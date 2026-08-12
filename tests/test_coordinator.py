"""Tests for coordinator failure and repair behavior."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neis_school.api import (
    NeisAuthenticationError,
    NeisConnectionError,
)
from custom_components.neis_school.const import (
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_KIND,
    DOMAIN,
    ISSUE_INCOMPLETE_DATA,
)
from custom_components.neis_school.coordinator import NeisSchoolCoordinator
from custom_components.neis_school.models import NeisResponse


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_OFFICE_CODE: "C10",
            CONF_SCHOOL_CODE: "7201202",
            CONF_SCHOOL_KIND: "초등학교",
        },
        options={CONF_GRADE: 6, CONF_CLASS_NAME: "2"},
    )


def _api(error: Exception):
    empty = NeisResponse.empty()
    return SimpleNamespace(
        has_api_key=True,
        get_meals_range=AsyncMock(side_effect=error),
        get_schedule=AsyncMock(return_value=empty),
        get_timetable_range=AsyncMock(return_value=empty),
    )


async def test_auth_failure_requests_reauthentication(hass) -> None:
    coordinator = NeisSchoolCoordinator(
        hass,
        _entry(),
        _api(NeisAuthenticationError("ERROR-290", "invalid")),
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    assert coordinator.last_error == "NeisAuthenticationError"
    assert coordinator.consecutive_failures == 1


async def test_connection_failure_is_not_reported_as_success(hass) -> None:
    coordinator = NeisSchoolCoordinator(
        hass,
        _entry(),
        _api(NeisConnectionError("offline")),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.last_error == "NeisConnectionError"
    assert coordinator.consecutive_failures == 1
    coordinator.async_shutdown()


async def test_entry_scoped_repair_issue_can_be_cleared(hass) -> None:
    entry = _entry()
    coordinator = NeisSchoolCoordinator(
        hass,
        entry,
        _api(NeisConnectionError("unused")),
    )
    issue_id = f"{ISSUE_INCOMPLETE_DATA}_{entry.entry_id}"
    registry = ir.async_get(hass)

    coordinator._update_incomplete_issue({"schedule_today"})
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    coordinator.clear_incomplete_issue()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_refresh_uses_three_rolling_requests_and_splits_dates(hass) -> None:
    today = datetime.fromisoformat("2026-08-13T05:05:00+09:00")
    meals = NeisResponse(
        ({"MLSV_YMD": "20260813", "MMEAL_SC_CODE": "2"},),
        1,
        True,
        "INFO-000",
    )
    schedules = NeisResponse.empty()
    timetables = NeisResponse(
        ({"ALL_TI_YMD": "20260814", "PERIO": "1", "ITRT_CNTNT": "국어"},),
        1,
        True,
        "INFO-000",
    )
    api = SimpleNamespace(
        has_api_key=True,
        get_meals_range=AsyncMock(return_value=meals),
        get_schedule=AsyncMock(return_value=schedules),
        get_timetable_range=AsyncMock(return_value=timetables),
    )
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)

    with patch(
        "custom_components.neis_school.coordinator.dt_util.now",
        return_value=today,
    ):
        data = await coordinator._async_update_data()

    api.get_meals_range.assert_awaited_once()
    api.get_schedule.assert_awaited_once()
    api.get_timetable_range.assert_awaited_once()
    assert len(data.meals) == 7
    assert len(data.timetables) == 7
    assert len(data.schedules) == 91
    assert data.meals[today.date()].rows[0]["MMEAL_SC_CODE"] == "2"
    assert data.timetables[today.date()].rows == ()
    assert data.timetables[today.date().replace(day=14)].rows[0]["PERIO"] == "1"

    coordinator.async_set_updated_data(data)
    await coordinator.async_project_date(today.date().replace(day=14))
    assert coordinator.data.local_date == today.date().replace(day=14)
    assert api.get_meals_range.await_count == 1


async def test_partial_failure_retains_complete_cached_source(hass) -> None:
    today = datetime.fromisoformat("2026-08-13T17:05:00+09:00")
    complete = NeisResponse.empty()
    api = SimpleNamespace(
        has_api_key=True,
        get_meals_range=AsyncMock(return_value=complete),
        get_schedule=AsyncMock(return_value=complete),
        get_timetable_range=AsyncMock(return_value=complete),
    )
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)
    with patch(
        "custom_components.neis_school.coordinator.dt_util.now",
        return_value=today,
    ):
        coordinator.data = await coordinator._async_update_data()
        api.get_meals_range.side_effect = NeisConnectionError("offline")
        data = await coordinator._async_update_data()

    assert data.meals == coordinator.data.meals
    assert data.incomplete_sources == {"meals"}
    assert coordinator.using_cached_data is True
    assert coordinator.consecutive_failures == 1
    coordinator.async_shutdown()


async def test_limited_mode_keeps_exact_today_and_tomorrow_queries(hass) -> None:
    today = datetime.fromisoformat("2026-08-13T05:05:00+09:00")
    complete = NeisResponse.empty()
    api = SimpleNamespace(
        has_api_key=False,
        get_meals=AsyncMock(return_value=complete),
        get_schedule=AsyncMock(return_value=complete),
        get_timetable=AsyncMock(return_value=complete),
    )
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)
    with patch(
        "custom_components.neis_school.coordinator.dt_util.now",
        return_value=today,
    ):
        data = await coordinator._async_update_data()

    assert api.get_meals.await_count == 2
    assert api.get_schedule.await_count == 2
    assert api.get_timetable.await_count == 2
    assert set(data.meals) == {today.date(), today.date().replace(day=14)}
    assert data.upcoming_schedule.result_code == "LIMITED_MODE"
