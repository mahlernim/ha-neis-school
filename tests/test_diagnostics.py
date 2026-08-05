"""Tests for privacy-safe downloaded diagnostics."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from custom_components.neis_school.const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
)
from custom_components.neis_school.diagnostics import (
    MAX_SAMPLE_ROWS,
    _response_diagnostics,
    async_get_config_entry_diagnostics,
)
from custom_components.neis_school.models import NeisCoordinatorData, NeisResponse


def _response(row_count: int = 1) -> NeisResponse:
    return NeisResponse(
        tuple(
            {
                "SD_SCHUL_CODE": "private-school-code",
                "SCHUL_NM": "Private School",
                "ORG_RDNMA": "Private school address",
                "EVENT_NM": f"Public event {index}",
            }
            for index in range(row_count)
        ),
        row_count,
        True,
        "INFO-000",
    )


def test_response_diagnostics_redacts_and_bounds_samples() -> None:
    result = _response_diagnostics(_response(MAX_SAMPLE_ROWS + 2))
    serialized = json.dumps(result, ensure_ascii=False)

    assert "private-school-code" not in serialized
    assert "Private School" not in serialized
    assert "Private school address" not in serialized
    assert "Public event 0" in serialized
    assert len(result["sample_rows"]) == MAX_SAMPLE_ROWS
    assert result["sample_truncated_count"] == 2
    assert result["returned_count"] == MAX_SAMPLE_ROWS + 2


@pytest.mark.asyncio
async def test_config_entry_diagnostics_never_exposes_credentials_or_school() -> None:
    local_date = date(2026, 8, 5)
    timestamp = datetime(2026, 8, 5, 1, 2, 3, tzinfo=UTC)
    response = _response()
    data = NeisCoordinatorData(
        local_date=local_date,
        meals={local_date: response},
        schedules={local_date: response},
        timetables={local_date: response},
        upcoming_schedule=response,
        last_success=timestamp,
        last_attempt=timestamp,
    )
    entry = SimpleNamespace(
        title="Private School 1-1",
        data={
            CONF_OFFICE_CODE: "C10",
            CONF_SCHOOL_CODE: "private-school-code",
            CONF_SCHOOL_NAME: "Private School",
            CONF_SCHOOL_KIND: "초등학교",
            CONF_SCHOOL_HOMEPAGE: "https://private-school.example",
        },
        options={
            CONF_API_KEY: "secret-api-key",
            CONF_GRADE: 1,
            CONF_CLASS_NAME: "1",
        },
        runtime_data=SimpleNamespace(data=data),
    )

    result = await async_get_config_entry_diagnostics(None, entry)
    serialized = json.dumps(result, ensure_ascii=False)

    assert "secret-api-key" not in serialized
    assert "private-school-code" not in serialized
    assert "Private School" not in serialized
    assert "private-school.example" not in serialized
    assert result["entry"]["api_key_configured"] is True
    assert result["runtime"]["last_error"] is None
    assert result["runtime"]["retained_after_error"] is False
