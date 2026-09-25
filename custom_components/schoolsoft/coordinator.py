"""Coordinator for SchoolSoft timetable and attendance information."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import Lesson, SchoolSoftClient, SchoolSoftError, apply_attendance
from .const import DOMAIN


class SchoolSoftCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Periodically fetch the current, previous and next school week."""

    def __init__(self, hass: HomeAssistant, session: ClientSession, data: dict[str, Any], interval) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN, update_interval=interval)
        self.client = SchoolSoftClient(session, data)

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        lessons: list[Lesson] = []
        attendance_text = ""
        try:
            if self.client.has_ical:
                iso = now.date().isocalendar()
                _, attendance_text, records = await self.client.async_fetch_week(iso.week, iso.year)
                lessons = apply_attendance(await self.client.async_fetch_ical(), records)
            else:
                for offset in (-1, 0, 1):
                    target = now.date().fromordinal(now.date().toordinal() + offset * 7)
                    iso = target.isocalendar()
                    week_lessons, page_text, records = await self.client.async_fetch_week(iso.week, iso.year)
                    lessons.extend(apply_attendance(week_lessons, records))
                    if offset == 0:
                        attendance_text = page_text
        except SchoolSoftError as err:
            raise UpdateFailed(str(err)) from err
        return {"lessons": sorted(set(lessons), key=lambda x: (x.start, x.end, x.summary)), "attendance": _attendance(attendance_text)}


def _attendance(text: str) -> dict[str, Any]:
    """Extract Swedish attendance notices without making guesses about attendance."""
    lower = text.lower()
    late = _minutes(r"sen ankomst\s*:\s*(\d+)\s*min", lower)
    out = _minutes(r"(?:ute|gick tidigare|lämnade)\s*:\s*(\d+)\s*min", lower)
    absence = any(word in lower for word in ("frånvaro", "franvaro", "sjuk", "ogiltig frånvaro"))
    activity = any(word in lower for word in ("annan skolaktivitet", "skolaktivitet", "studiebesök"))
    return {"late_minutes": late, "out_minutes": out, "absence": absence, "other_school_activity": activity}


def _minutes(pattern: str, value: str) -> int:
    match = re.search(pattern, value)
    return int(match.group(1)) if match else 0
