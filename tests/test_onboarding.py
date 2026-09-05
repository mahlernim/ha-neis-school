"""Regression tests for setup recovery, validation, and profile confirmation."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neis_school.api import (
    NeisApiError,
    NeisAuthenticationError,
    NeisConnectionError,
    NeisRateLimitError,
)
from custom_components.neis_school.const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_LIMITED_ACK,
    CONF_MEAL_TYPES,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
    DOMAIN,
)
from custom_components.neis_school.models import NeisResponse

SCHOOL = {
    "SD_SCHUL_CODE": "test-school",
    "SCHUL_NM": "테스트초등학교",
    "SCHUL_KND_SC_NM": "초등학교",
    "ORG_RDNMA": "테스트시 학교로",
}
SEARCH = {CONF_OFFICE_CODE: "C10", CONF_SCHOOL_NAME: "테스트초등학교"}
SCHOOLS = NeisResponse((SCHOOL,), 1, True, "INFO-000")
CLASSES = NeisResponse(({"CLASS_NM": "1"}, {"CLASS_NM": "2"}), 2, True, "INFO-000")
FLOW_PATH = "custom_components.neis_school.config_flow"


@pytest.fixture(autouse=True)
def fixed_academic_year():
    with patch(f"{FLOW_PATH}._academic_year", return_value=2026):
        yield


async def _start(hass, *, limited=False):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "" if limited else "test-key", CONF_LIMITED_ACK: limited},
    )


async def _class_step(hass, *, limited=False):
    result = await _start(hass, limited=limited)
    with patch(f"{FLOW_PATH}.NeisAPI.search_schools", return_value=SCHOOLS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SEARCH
        )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_GRADE: "6"}
    )


def _field(result, name):
    return next(field for field in result["data_schema"].schema if str(field) == name)


async def test_blank_school_is_rejected_before_search(hass):
    result = await _start(hass)
    with patch(f"{FLOW_PATH}.NeisAPI.search_schools") as search:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SEARCH, CONF_SCHOOL_NAME: "   "}
        )
    assert result["errors"] == {CONF_SCHOOL_NAME: "required"}
    search.assert_not_awaited()


async def test_partial_school_search_does_not_auto_select(hass):
    result = await _start(hass, limited=True)
    partial = NeisResponse((SCHOOL,), 20, False, "INFO-000")
    with patch(f"{FLOW_PATH}.NeisAPI.search_schools", return_value=partial):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SEARCH
        )
    assert result["step_id"] == "school"
    assert result["errors"] == {"base": "incomplete_school_search"}
    assert (
        _field(result, CONF_SCHOOL_NAME).description["suggested_value"]
        == SEARCH[CONF_SCHOOL_NAME]
    )


async def test_school_retry_preserves_query_and_office(hass):
    result = await _start(hass)
    with patch(
        f"{FLOW_PATH}.NeisAPI.search_schools",
        side_effect=NeisConnectionError("offline"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SEARCH
        )
    assert result["errors"] == {"base": "cannot_connect"}
    for name, value in SEARCH.items():
        assert _field(result, name).description["suggested_value"] == value


async def test_correcting_key_resumes_school_search(hass):
    result = await _start(hass)
    with patch(
        f"{FLOW_PATH}.NeisAPI.search_schools",
        side_effect=[NeisAuthenticationError("ERROR-290", "invalid"), SCHOOLS],
    ) as search:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SEARCH
        )
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_API_KEY: "invalid_auth"}
        assert not _field(result, CONF_API_KEY).description
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "replacement-key"}
        )
    assert result["step_id"] == "grade"
    assert search.await_count == 2
    assert search.call_args.args == ("C10", "테스트초등학교")
    assert result["description_placeholders"]["school_name"] == SCHOOL["SCHUL_NM"]


@pytest.mark.parametrize("during_selection", [False, True])
async def test_correcting_key_resumes_class_profile(hass, during_selection):
    error = NeisAuthenticationError("ERROR-290", "invalid")
    responses = [CLASSES, error, CLASSES] if during_selection else [error, CLASSES]
    with patch(f"{FLOW_PATH}.NeisAPI.get_classes", side_effect=responses) as classes:
        result = await _class_step(hass)
        if during_selection:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_CLASS_NAME: "2"}
            )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "replacement-key"}
        )
    assert result["step_id"] == "class"
    assert result["description_placeholders"]["grade"] == "6"
    assert classes.call_args.args[1:4] == ("test-school", 2026, 6)
    if during_selection:
        assert _field(result, CONF_CLASS_NAME).default() == "2"


async def test_blank_manual_class_does_not_query_all_classes(hass):
    with patch(f"{FLOW_PATH}.NeisAPI.get_classes") as classes:
        result = await _class_step(hass, limited=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "   "}
        )
    assert result["errors"] == {CONF_CLASS_NAME: "required"}
    classes.assert_not_awaited()


@pytest.mark.parametrize(
    "mismatch",
    [
        {"CLASS_NM": "3"},
        {"GRADE": "5"},
        {"SD_SCHUL_CODE": "other-school"},
        {"ATPT_OFCDC_SC_CODE": "B10"},
        {"AY": "2025"},
    ],
)
async def test_unrelated_class_response_is_rejected(hass, mismatch):
    row = {"CLASS_NM": "2", **mismatch}
    with patch(
        f"{FLOW_PATH}.NeisAPI.get_classes",
        return_value=NeisResponse((row,), 1, True, "INFO-000"),
    ):
        result = await _class_step(hass, limited=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
    assert result["errors"] == {CONF_CLASS_NAME: "class_not_found"}


@pytest.mark.parametrize(
    "first_response, expected_error",
    [
        (NeisResponse.empty(), "classes_unavailable"),
        (NeisConnectionError("offline"), "cannot_connect"),
        (NeisRateLimitError("ERROR-337", "limit"), "rate_limited"),
        (NeisApiError("ERROR-500", "unavailable"), "api_error"),
        (NeisResponse((), 10, False, "INFO-000"), "incomplete_data"),
    ],
)
async def test_class_list_failure_can_retry_without_entering_a_class(
    hass, first_response, expected_error
):
    with patch(
        f"{FLOW_PATH}.NeisAPI.get_classes", side_effect=[first_response, CLASSES]
    ) as classes:
        result = await _class_step(hass)
        assert result["errors"] == {"base": expected_error}
        assert CONF_CLASS_NAME not in result["data_schema"].schema
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_GRADE: "6"}
        )
    assert result["step_id"] == "class"
    assert result["errors"] == {}
    assert CONF_CLASS_NAME in result["data_schema"].schema
    assert classes.await_count == 2


async def test_class_verification_failure_preserves_dropdown_and_selection(hass):
    with patch(
        f"{FLOW_PATH}.NeisAPI.get_classes",
        side_effect=[CLASSES, NeisConnectionError("offline"), CLASSES],
    ):
        result = await _class_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
        assert result["errors"] == {"base": "cannot_connect"}
        field = _field(result, CONF_CLASS_NAME)
        assert result["data_schema"].schema[field].container == {"1": "1", "2": "2"}
        assert field.default() == "2"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
    assert result["step_id"] == "meals"


async def test_grade_can_change_without_submitting_a_class(hass):
    with patch(f"{FLOW_PATH}.NeisAPI.get_classes", return_value=CLASSES) as classes:
        result = await _class_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_GRADE: "5"}
        )
    assert result["step_id"] == "class"
    assert result["description_placeholders"]["grade"] == "5"
    assert classes.call_args.args[3] == 5


async def test_limited_class_data_can_upgrade_to_an_api_key(hass):
    with patch(
        f"{FLOW_PATH}.NeisAPI.get_classes",
        side_effect=[NeisResponse((), 10, False, "INFO-000"), CLASSES],
    ):
        result = await _class_step(hass, limited=True)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-key"}
        )
    assert result["step_id"] == "class"
    assert _field(result, CONF_CLASS_NAME).default() == "2"


@pytest.mark.parametrize("limited", [False, True])
async def test_final_summary_and_entry_match_the_selected_profile(hass, limited):
    with (
        patch(f"{FLOW_PATH}.NeisAPI.get_classes", return_value=CLASSES),
        patch("custom_components.neis_school.async_setup_entry", return_value=True),
    ):
        result = await _class_step(hass, limited=limited)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
        assert result["step_id"] == ("meals_limited" if limited else "meals")
        assert result["description_placeholders"] == {
            "school_name": SCHOOL["SCHUL_NM"],
            "school_address": SCHOOL["ORG_RDNMA"],
            "academic_year": "2026",
            "grade": "6",
            "class_name": "2",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_MEAL_TYPES: ["2"]}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_CLASS_NAME] == "2"
    assert result["options"][CONF_GRADE] == 6


@pytest.mark.parametrize("class_name", ["   ", "3"])
async def test_options_reject_blank_or_unmatched_class(hass, class_name):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_OFFICE_CODE: "C10",
            CONF_SCHOOL_CODE: "test-school",
            CONF_SCHOOL_NAME: SCHOOL["SCHUL_NM"],
            CONF_SCHOOL_KIND: SCHOOL["SCHUL_KND_SC_NM"],
            CONF_API_KEY: "test-key",
        },
        options={CONF_GRADE: 6, CONF_CLASS_NAME: "2", CONF_MEAL_TYPES: ["2"]},
    )
    entry.add_to_hass(hass)
    with patch(
        f"{FLOW_PATH}.NeisAPI.get_classes", AsyncMock(return_value=CLASSES)
    ) as classes:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_GRADE: "6", CONF_CLASS_NAME: class_name, CONF_MEAL_TYPES: ["2"]},
        )
    assert result["errors"] == {
        CONF_CLASS_NAME: "required" if not class_name.strip() else "class_not_found"
    }
    assert entry.options[CONF_CLASS_NAME] == "2"
    if not class_name.strip():
        classes.assert_not_awaited()
