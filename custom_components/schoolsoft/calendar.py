"""Calendar platform for SchoolSoft."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SchoolSoftConfigEntry
from .client import Lesson
from .coordinator import SchoolSoftCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SchoolSoftConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SchoolSoftCalendar(entry.runtime_data, entry.entry_id, entry.title)])


class SchoolSoftCalendar(CoordinatorEntity[SchoolSoftCoordinator], CalendarEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SchoolSoftCoordinator, entry_id: str, title: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_calendar"
        self._attr_name = title

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        for lesson in self.coordinator.data["lessons"]:
            if lesson.start <= now < lesson.end or lesson.start > now:
                return _event(lesson)
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [_event(item) for item in self.coordinator.data["lessons"] if item.start < end_date and item.end > start_date]

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()


def _event(lesson: Lesson) -> CalendarEvent:
    marker = {"absent": "[ABSENT] ", "late": "[LATE] "}.get(lesson.attendance, "")
    return CalendarEvent(summary=f"{marker}{lesson.summary}", start=lesson.start, end=lesson.end)
