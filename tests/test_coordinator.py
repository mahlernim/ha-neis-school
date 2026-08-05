"""Tests for coordinator failure and repair behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

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
        get_meals=AsyncMock(side_effect=error),
        get_schedule=AsyncMock(return_value=empty),
        get_timetable=AsyncMock(return_value=empty),
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
