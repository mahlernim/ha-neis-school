"""Tests for the user-facing configuration flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector

from custom_components.neis_school.const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_LIMITED_ACK,
    CONF_MEAL_TYPES,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_NAME,
    DOMAIN,
)
from custom_components.neis_school.models import NeisResponse


def test_academic_year_uses_march_boundary() -> None:
    from datetime import date

    from custom_components.neis_school.config_flow import _academic_year

    assert _academic_year(date(2026, 2, 28)) == 2025
    assert _academic_year(date(2026, 3, 1)) == 2026


def test_grade_schema_is_a_school_specific_dropdown() -> None:
    from custom_components.neis_school.config_flow import _grade_schema

    elementary = _grade_schema("초등학교")
    middle = _grade_schema("중학교")

    assert isinstance(elementary.validators[0], SelectSelector)
    assert elementary.validators[0].config["mode"] == "dropdown"
    assert elementary.validators[0].config["options"] == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
    ]
    assert middle.validators[0].config["options"] == ["1", "2", "3"]
    assert elementary("6") == 6


async def test_limited_mode_requires_acknowledgement(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "", CONF_LIMITED_ACK: False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "limited_not_acknowledged"}


async def test_limited_mode_continues_after_acknowledgement(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "", CONF_LIMITED_ACK: True}
    )
    assert result["step_id"] == "school"


async def test_complete_setup_with_api_key(hass) -> None:
    school = {
        "ATPT_OFCDC_SC_CODE": "C10",
        "SD_SCHUL_CODE": "7201202",
        "SCHUL_NM": "화정초등학교",
        "SCHUL_KND_SC_NM": "초등학교",
        "HMPG_ADRES": "https://example.invalid",
        "ORG_RDNMA": "부산광역시 북구",
    }
    schools = NeisResponse((school,), 1, True, "INFO-000")
    classes = NeisResponse(({"CLASS_NM": "1"}, {"CLASS_NM": "2"}), 2, True, "INFO-000")
    with (
        patch(
            "custom_components.neis_school.config_flow.NeisAPI.search_schools",
            AsyncMock(return_value=schools),
        ),
        patch(
            "custom_components.neis_school.config_flow.NeisAPI.get_classes",
            AsyncMock(return_value=classes),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "x" * 32, CONF_LIMITED_ACK: False}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_OFFICE_CODE: "C10", CONF_SCHOOL_NAME: "화정초등학교"},
        )
        assert result["step_id"] == "grade"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_GRADE: "6"}
        )
        assert result["step_id"] == "class"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CLASS_NAME: "2"}
        )
        assert result["step_id"] == "meals"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_MEAL_TYPES: ["2"]}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCHOOL_CODE] == "7201202"
    assert result["options"][CONF_GRADE] == 6
    assert result["options"][CONF_CLASS_NAME] == "2"
