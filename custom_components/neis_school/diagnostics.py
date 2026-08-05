"""Diagnostics for NEIS School."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_NAME,
)
from .coordinator import NeisSchoolCoordinator
from .models import NeisResponse

MAX_SAMPLE_ROWS = 10
ENTRY_REDACT_KEYS = {
    "title",
    CONF_API_KEY,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_NAME,
}
ROW_REDACT_KEYS = {
    "SD_SCHUL_CODE",
    "SCHUL_NM",
    "HMPG_ADRES",
    "ORG_RDNMA",
    "ORG_RDNDA",
}


def _response_diagnostics(response: NeisResponse) -> dict[str, Any]:
    """Return bounded, privacy-safe API response diagnostics."""
    sample = [dict(row) for row in response.rows[:MAX_SAMPLE_ROWS]]
    return {
        "result_code": response.result_code,
        "returned_count": len(response.rows),
        "total_count": response.total_count,
        "complete": response.complete,
        "sample_rows": async_redact_data(
            {"rows": sample}, ROW_REDACT_KEYS
        )["rows"],
        "sample_truncated_count": max(0, len(response.rows) - len(sample)),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return credential-free diagnostics."""
    coordinator: NeisSchoolCoordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
                "api_key_configured": bool(entry.options.get(CONF_API_KEY)),
            },
            ENTRY_REDACT_KEYS,
        ),
        "profile": {
            "grade": entry.options[CONF_GRADE],
            "class": entry.options[CONF_CLASS_NAME],
        },
        "runtime": {
            "local_date": data.local_date.isoformat(),
            "last_success": data.last_success.isoformat(),
            "last_attempt": data.last_attempt.isoformat(),
            "last_error": data.last_error,
            "retained_after_error": data.retained_after_error,
            "incomplete_sources": sorted(data.incomplete_sources),
            "meals": {
                day.isoformat(): _response_diagnostics(response)
                for day, response in data.meals.items()
            },
            "schedules": {
                day.isoformat(): _response_diagnostics(response)
                for day, response in data.schedules.items()
            },
            "timetables": {
                day.isoformat(): _response_diagnostics(response)
                for day, response in data.timetables.items()
            },
            "upcoming_schedule": _response_diagnostics(data.upcoming_schedule),
        },
    }
