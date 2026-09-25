"""Authenticated SchoolSoft guardian client and timetable parser."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from html.parser import HTMLParser
import re
from typing import Any

from aiohttp import ClientSession
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import dt as dt_util

from .const import CONF_SCHOOL_URL

_TIME_RANGE = re.compile(r"(?P<start>\d{1,2}:\d{2})\s*[-–]\s*(?P<end>\d{1,2}:\d{2})\s*(?P<title>.*?)(?=\s+\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}|$)")
_DAY = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Måndag|Tisdag|Onsdag|Torsdag|Fredag|Lördag|Söndag)\b", re.I)
_IGNORE = {"lunch", "rast", "break"}
_GRID_SUFFIX = re.compile(
    r"\s+\d{1,2}:\d{2}(?:\s+\d{1,2}:\d{2})*(?:\s+(?:Må|Ti|On|To|Fr|Lö|Sö|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|v\d+).*)?$",
    re.I,
)
_SWEDISH_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
_ATTENDANCE_LINE = re.compile(
    r"(?:(?:Idag|Igår)\s+)?(?:(?:Mån|Tis|Ons|Tor|Fre|Lör|Lö|Sön)\s+)?"
    r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-zåäö]+)\.?\s+"
    r"(?P<time>\d{1,2}:\d{2})\s+(?P<subject>\S+)\s+(?P<status>.+)",
    re.I,
)


class SchoolSoftError(Exception):
    """Base SchoolSoft error."""


class SchoolSoftAuthenticationError(SchoolSoftError):
    """Guardian credentials or session are invalid."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


class _AttendanceExtractor(HTMLParser):
    """Extract the text of individual lesson-status links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._parts: list[str] = []
        self.records: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href", "") or ""
        if "right_student_lesson_status.jsp" in href:
            self._capturing = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capturing:
            self.records.append(" ".join(" ".join(self._parts).split()))
            self._capturing = False


@dataclass(frozen=True, slots=True)
class Lesson:
    """One lesson from the weekly SchoolSoft page."""

    summary: str
    start: datetime
    end: datetime
    attendance: str | None = None


@dataclass(frozen=True, slots=True)
class AttendanceRecord:
    """An attendance status linked by SchoolSoft to one lesson."""

    day: int
    month: int
    start: time
    subject: str
    status: str


class SchoolSoftClient:
    """Fetch SchoolSoft's guardian-only weekly timetable."""

    def __init__(self, session: ClientSession, data: dict[str, Any]) -> None:
        self._session = session
        self._data = data
        self._base = data[CONF_SCHOOL_URL].rstrip("/")
        self._logged_in = False
        self._lock = asyncio.Lock()

    async def async_login(self) -> None:
        """Create a guardian (usertype 2) web session."""
        async with self._lock:
            async with self._session.get(f"{self._base}/jsp/Login.jsp", timeout=20) as response:
                await response.read()
            payload = {
                "action": "login", "usertype": "2",
                "ssusername": self._data[CONF_USERNAME],
                "sspassword": self._data[CONF_PASSWORD],
                "button": "Logga in",
            }
            async with self._session.post(f"{self._base}/jsp/Login.jsp", data=payload, allow_redirects=False, timeout=20) as response:
                await response.read()
                if response.status not in (301, 302, 303):
                    raise SchoolSoftAuthenticationError("Guardian login was rejected")
            if not await self._async_session_valid():
                raise SchoolSoftAuthenticationError("Guardian session validation failed")
            self._logged_in = True

    async def _async_session_valid(self) -> bool:
        async with self._session.get(f"{self._base}/rest-api/session", timeout=20) as response:
            if response.status != 200:
                return False
            try:
                payload = await response.json(content_type=None)
            except (ValueError, TypeError):
                return False
        return bool(payload.get("user"))

    async def async_fetch_week(self, week: int, year: int) -> tuple[list[Lesson], str, list[AttendanceRecord]]:
        """Fetch and parse a week; reauthenticate once if the page session expires."""
        if not self._logged_in or not await self._async_session_valid():
            await self.async_login()
        url = f"{self._base}/jsp/student/right_student_startpage.jsp?view=week&week={week}"
        async with self._session.get(url, timeout=30) as response:
            html = await response.text()
            if response.status != 200 or "Login.jsp" in str(response.url):
                self._logged_in = False
                await self.async_login()
                async with self._session.get(url, timeout=30) as retry:
                    html = await retry.text()
                    if retry.status != 200:
                        raise SchoolSoftError(f"Timetable request failed: HTTP {retry.status}")
        return self._parse_week(html, week, year), _TextExtractorText(html).text, self._parse_attendance(html)

    @staticmethod
    def _parse_week(html: str, week: int, year: int) -> list[Lesson]:
        text = _TextExtractorText(html).text
        monday = date.fromisocalendar(year, week, 1)
        markers = list(_DAY.finditer(text))
        lessons: list[Lesson] = []
        for index, marker in enumerate(markers):
            chunk = text[marker.end(): markers[index + 1].start() if index + 1 < len(markers) else len(text)]
            day_index = next((i for i, name in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag")) if marker.group(0).lower() == name), 0) % 7
            lesson_date = monday + timedelta(days=day_index)
            for match in _TIME_RANGE.finditer(chunk):
                title = _GRID_SUFFIX.sub("", " ".join(match.group("title").split())).strip()
                if not title or title.lower() in _IGNORE or len(title) > 160:
                    continue
                start = datetime.combine(lesson_date, _parse_time(match.group("start")), dt_util.DEFAULT_TIME_ZONE)
                end = datetime.combine(lesson_date, _parse_time(match.group("end")), dt_util.DEFAULT_TIME_ZONE)
                if end > start:
                    lessons.append(Lesson(title, start, end))
        return sorted(set(lessons), key=lambda item: (item.start, item.end, item.summary))

    @staticmethod
    def _parse_attendance(html: str) -> list[AttendanceRecord]:
        parser = _AttendanceExtractor()
        parser.feed(html)
        records: list[AttendanceRecord] = []
        for value in parser.records:
            match = _ATTENDANCE_LINE.fullmatch(value)
            if not match:
                continue
            status = match.group("status").lower()
            if "sen ankomst" in status:
                kind = "late"
            elif "absent" in status or "frånvaro" in status or "franvaro" in status:
                kind = "absent"
            else:
                continue
            month = _SWEDISH_MONTHS.get(match.group("month").lower()[:3])
            if month:
                records.append(AttendanceRecord(int(match.group("day")), month, _parse_time(match.group("time")), match.group("subject"), kind))
        return records


def apply_attendance(lessons: list[Lesson], records: list[AttendanceRecord]) -> list[Lesson]:
    """Attach SchoolSoft's per-lesson late/absent status to the timetable."""
    marked: list[Lesson] = []
    for lesson in lessons:
        status = next((record.status for record in records if record.day == lesson.start.day and record.month == lesson.start.month and record.start == lesson.start.time().replace(tzinfo=None) and lesson.summary.casefold().startswith(record.subject.casefold())), None)
        marked.append(Lesson(lesson.summary, lesson.start, lesson.end, status))
    return marked


class _TextExtractorText:
    """Small helper kept separate to make parser calls concise."""
    def __init__(self, html: str) -> None:
        parser = _TextExtractor()
        parser.feed(html)
        self.text = parser.text


def _parse_time(value: str) -> time:
    """Parse SchoolSoft times, which may have a one-digit hour."""
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))
