"""Diagnostics for NEIS School."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_CLASS_NAME, CONF_GRADE
from .coordinator import NeisSchoolCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return credential-free diagnostics."""
    coordinator: NeisSchoolCoordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": {
                key: value
                for key, value in entry.options.items()
                if key != CONF_API_KEY
            },
            "api_key_configured": bool(entry.options.get(CONF_API_KEY)),
        },
        "profile": {
            "grade": entry.options[CONF_GRADE],
            "class": entry.options[CONF_CLASS_NAME],
        },
        "runtime": {
            "local_date": data.local_date.isoformat(),
            "last_success": data.last_success.isoformat(),
            "incomplete_sources": sorted(data.incomplete_sources),
            "meal_counts": {
                day.isoformat(): len(response.rows)
                for day, response in data.meals.items()
            },
            "schedule_counts": {
                day.isoformat(): len(response.rows)
                for day, response in data.schedules.items()
            },
            "timetable_counts": {
                day.isoformat(): len(response.rows)
                for day, response in data.timetables.items()
            },
        },
    }
