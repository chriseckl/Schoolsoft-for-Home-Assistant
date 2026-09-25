"""Sensor platform for SchoolSoft."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SchoolSoftConfigEntry
from .coordinator import SchoolSoftCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SchoolSoftConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SchoolSoftSensor(entry.runtime_data, entry.entry_id, key, name, getter) for key, name, getter in _SENSORS])


class SchoolSoftSensor(CoordinatorEntity[SchoolSoftCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SchoolSoftCoordinator, entry_id: str, key: str, name: str, getter: Callable) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._getter = getter

    @property
    def native_value(self):
        return self._getter(self.coordinator.data)


def _current(data):
    now = dt_util.now()
    return next((x.summary for x in data["lessons"] if x.start <= now < x.end), None)


def _next(data):
    now = dt_util.now()
    return next((x.summary for x in data["lessons"] if x.start > now), None)


def _current_attendance(data):
    """Return only the attendance status for the lesson happening now."""
    now = dt_util.now()
    lesson = next((x for x in data["lessons"] if x.start <= now < x.end), None)
    return lesson.attendance if lesson and lesson.attendance else "none"


def _school_start(data):
    today = dt_util.now().date()
    values = [x.start.time().isoformat(timespec="minutes") for x in data["lessons"] if x.start.date() == today]
    return min(values) if values else None


def _school_end(data):
    today = dt_util.now().date()
    values = [x.end.time().isoformat(timespec="minutes") for x in data["lessons"] if x.end.date() == today]
    return max(values) if values else None


_SENSORS = [
    ("current_lesson", "Current lesson", _current), ("next_lesson", "Next lesson", _next),
    ("current_lesson_attendance", "Current lesson attendance", _current_attendance),
    ("school_start", "School start", _school_start), ("school_end", "School end", _school_end),
    ("absence", "Absence", lambda d: d["attendance"]["absence"]),
    ("late_arrival", "Late arrival", lambda d: d["attendance"]["late_minutes"]),
    ("out_early", "Left early / out", lambda d: d["attendance"]["out_minutes"]),
    ("other_school_activity", "Other school activity", lambda d: d["attendance"]["other_school_activity"]),
]
