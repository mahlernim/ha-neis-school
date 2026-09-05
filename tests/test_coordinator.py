"""Tests for coordinator failure and repair behavior."""

import asyncio
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


def _api(error: Exception | None):
    empty = NeisResponse.empty()
    return SimpleNamespace(
        has_api_key=True,
        get_meals_range=AsyncMock(side_effect=error, return_value=empty),
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
    await coordinator.async_shutdown()


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
    await coordinator.async_shutdown()


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


async def test_unloaded_coordinator_does_not_refresh_again(hass) -> None:
    """Unloading must shut down HA's debouncer as well as the custom retry."""
    entry = _entry()
    api = _api(NeisConnectionError("offline"))
    coordinator = NeisSchoolCoordinator(hass, entry, api)
    await coordinator.async_refresh()
    assert coordinator._cancel_retry is not None
    assert api.get_meals_range.await_count == 1

    await entry._async_process_on_unload(hass)
    assert coordinator._cancel_retry is None
    await coordinator.async_refresh()

    try:
        assert api.get_meals_range.await_count == 1
    finally:
        if coordinator._cancel_retry is not None:
            coordinator._cancel_retry()


@pytest.mark.parametrize(
    "changed_field, changed_value",
    [
        (CONF_GRADE, 5),
        (CONF_CLASS_NAME, "3"),
        (CONF_OFFICE_CODE, "B10"),
        (CONF_SCHOOL_CODE, "other-school"),
        (CONF_SCHOOL_KIND, "중학교"),
        ("api_mode", "limited"),
        ("legacy", None),
    ],
)
async def test_snapshot_for_another_profile_is_not_restored(
    hass, changed_field, changed_value
) -> None:
    """Cached lessons must belong to the currently configured student profile."""
    now = datetime.fromisoformat("2026-09-07T05:05:00+09:00")
    api = _api(None)
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)
    with patch(
        "custom_components.neis_school.coordinator.dt_util.now", return_value=now
    ):
        data = await coordinator._async_update_data()

    profile = {
        CONF_OFFICE_CODE: "C10",
        CONF_SCHOOL_CODE: "7201202",
        CONF_SCHOOL_KIND: "초등학교",
        CONF_GRADE: 6,
        CONF_CLASS_NAME: "2",
        "api_mode": "full",
    }
    stored = {"profile": profile, "snapshot": data.as_dict()}
    if changed_field == "legacy":
        stored.pop("profile")
    else:
        profile[changed_field] = changed_value

    with (
        patch.object(coordinator.store, "async_load", return_value=stored),
        patch.object(coordinator, "async_config_entry_first_refresh") as first_refresh,
        patch.object(coordinator, "async_request_refresh") as background_refresh,
        patch(
            "custom_components.neis_school.coordinator.dt_util.now", return_value=now
        ),
    ):
        await coordinator.async_initialize()
        await hass.async_block_till_done()

    first_refresh.assert_awaited_once()
    background_refresh.assert_not_awaited()
    assert coordinator.data is None
    assert coordinator.using_cached_data is False


async def test_matching_snapshot_restores_and_refreshes_in_background(hass) -> None:
    """An unchanged profile should retain fast startup using its saved snapshot."""
    now = datetime.fromisoformat("2026-09-07T05:05:00+09:00")
    api = _api(None)
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)
    with (
        patch.object(coordinator.store, "async_save") as save,
        patch(
            "custom_components.neis_school.coordinator.dt_util.now", return_value=now
        ),
    ):
        data = await coordinator._async_update_data()
    stored = save.call_args.args[0]

    with (
        patch.object(coordinator.store, "async_load", return_value=stored),
        patch.object(coordinator, "async_config_entry_first_refresh") as first_refresh,
        patch.object(coordinator, "async_request_refresh") as background_refresh,
        patch(
            "custom_components.neis_school.coordinator.dt_util.now", return_value=now
        ),
    ):
        await coordinator.async_initialize()
        await hass.async_block_till_done()

    first_refresh.assert_not_awaited()
    background_refresh.assert_awaited_once()
    assert coordinator.data == data
    assert coordinator.using_cached_data is True


async def test_successful_refresh_does_not_disable_future_updates(hass) -> None:
    """Clearing a recovery timer must not shut down the coordinator."""
    api = _api(None)
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)

    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert api.get_meals_range.await_count == 2


async def test_inflight_failure_does_not_schedule_retry_after_unload(hass) -> None:
    """A request finishing during unload must not restart background recovery."""
    started = asyncio.Event()
    finish = asyncio.Event()

    async def fail_after_unload(*args):
        started.set()
        await finish.wait()
        raise NeisConnectionError("offline")

    entry = _entry()
    api = _api(None)
    api.get_meals_range.side_effect = fail_after_unload
    coordinator = NeisSchoolCoordinator(hass, entry, api)
    refresh = hass.async_create_task(coordinator.async_refresh())
    await started.wait()
    await entry._async_process_on_unload(hass)
    finish.set()
    await refresh

    try:
        assert coordinator._cancel_retry is None
    finally:
        if coordinator._cancel_retry is not None:
            coordinator._cancel_retry()


async def test_authentication_failure_cancels_pending_recovery(hass) -> None:
    """Recovery for a transient outage must stop once credentials are rejected."""
    api = _api(NeisConnectionError("offline"))
    coordinator = NeisSchoolCoordinator(hass, _entry(), api)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator._cancel_retry is not None

    api.get_meals_range.side_effect = NeisAuthenticationError("ERROR-290", "invalid")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    try:
        assert coordinator._cancel_retry is None
    finally:
        if coordinator._cancel_retry is not None:
            coordinator._cancel_retry()
