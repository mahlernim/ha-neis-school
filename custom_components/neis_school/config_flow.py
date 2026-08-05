"""Config flow for NEIS School."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeisAPI, NeisApiError, NeisConnectionError
from .const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_LIMITED_ACK,
    CONF_MEAL_TYPES,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
    DEFAULT_MEAL_TYPES,
    DOMAIN,
    MEAL_TYPES,
    OFFICES,
    SCHOOL_KIND_ENDPOINTS,
)

API_KEY_URL = "https://open.neis.go.kr/portal/guide/actKeyPage.do"


def _academic_year(today: date | None = None) -> int:
    """Return the Korean academic year for a date."""
    current = today or date.today()
    return current.year if current.month >= 3 else current.year - 1


def _password_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


def _meal_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(MEAL_TYPES),
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
            translation_key=CONF_MEAL_TYPES,
        )
    )


class NeisSchoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a NEIS School config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize transient flow state."""
        self._api_key: str | None = None
        self._api: NeisAPI | None = None
        self._office_code = ""
        self._schools: dict[str, dict[str, Any]] = {}
        self._school: dict[str, Any] = {}
        self._grade = 0
        self._class_name = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect an optional API key and limitation acknowledgement."""
        errors: dict[str, str] = {}
        if user_input is not None:
            value = str(user_input.get(CONF_API_KEY, "")).strip()
            if not value and not user_input.get(CONF_LIMITED_ACK, False):
                errors["base"] = "limited_not_acknowledged"
            else:
                self._api_key = value or None
                self._api = NeisAPI(async_get_clientsession(self.hass), self._api_key)
                return await self.async_step_school()

        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY): _password_selector(),
                vol.Optional(CONF_LIMITED_ACK, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_school(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Search for a school."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._office_code = str(user_input[CONF_OFFICE_CODE])
            try:
                assert self._api is not None
                result = await self._api.search_schools(
                    self._office_code, str(user_input[CONF_SCHOOL_NAME]).strip()
                )
            except NeisApiError:
                errors["base"] = "api_error"
            except NeisConnectionError:
                errors["base"] = "cannot_connect"
            else:
                supported = {
                    str(row["SD_SCHUL_CODE"]): row
                    for row in result.rows
                    if row.get("SCHUL_KND_SC_NM") in SCHOOL_KIND_ENDPOINTS
                }
                if not supported:
                    errors["base"] = "school_not_found"
                else:
                    self._schools = supported
                    if len(supported) == 1:
                        self._school = next(iter(supported.values()))
                        return await self._after_school_selected()
                    return await self.async_step_select_school()

        schema = vol.Schema(
            {
                vol.Required(CONF_OFFICE_CODE): vol.In(OFFICES),
                vol.Required(CONF_SCHOOL_NAME): str,
            }
        )
        return self.async_show_form(step_id="school", data_schema=schema, errors=errors)

    async def async_step_select_school(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user choose among school search results."""
        if user_input is not None:
            self._school = self._schools[str(user_input[CONF_SCHOOL_CODE])]
            return await self._after_school_selected()
        choices = {
            code: f"{row.get('SCHUL_NM')} · {row.get('ORG_RDNMA', '')}"
            for code, row in self._schools.items()
        }
        return self.async_show_form(
            step_id="select_school",
            data_schema=vol.Schema({vol.Required(CONF_SCHOOL_CODE): vol.In(choices)}),
        )

    async def _after_school_selected(self) -> FlowResult:
        """Set uniqueness and continue with the student profile."""
        school_code = str(self._school["SD_SCHUL_CODE"])
        await self.async_set_unique_id(school_code)
        self._abort_if_unique_id_configured()
        return await self.async_step_grade()

    async def async_step_grade(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect the student's grade."""
        if user_input is not None:
            self._grade = int(user_input[CONF_GRADE])
            return await self.async_step_class()
        return self.async_show_form(
            step_id="grade",
            data_schema=vol.Schema(
                {vol.Required(CONF_GRADE): vol.All(vol.Coerce(int), vol.Range(1, 6))}
            ),
        )

    async def async_step_class(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose or enter a class and validate it."""
        errors: dict[str, str] = {}
        assert self._api is not None
        if user_input is None and self._api.has_api_key:
            try:
                result = await self._api.get_classes(
                    self._office_code,
                    str(self._school["SD_SCHUL_CODE"]),
                    _academic_year(),
                    self._grade,
                )
            except NeisConnectionError:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
                    errors={"base": "cannot_connect"},
                )
            except NeisApiError:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
                    errors={"base": "api_error"},
                )
            choices = {
                str(row["CLASS_NM"]): str(row["CLASS_NM"]) for row in result.rows
            }
            if choices:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_CLASS_NAME): vol.In(choices)}
                    ),
                )

        if user_input is not None:
            class_name = str(user_input[CONF_CLASS_NAME]).strip()
            try:
                result = await self._api.get_classes(
                    self._office_code,
                    str(self._school["SD_SCHUL_CODE"]),
                    _academic_year(),
                    self._grade,
                    class_name,
                )
            except NeisConnectionError:
                errors["base"] = "cannot_connect"
            except NeisApiError:
                errors["base"] = "api_error"
            else:
                if not result.rows:
                    errors["base"] = "class_not_found"
                elif not result.complete:
                    errors["base"] = "incomplete_data"
                else:
                    self._class_name = class_name
                    return await self.async_step_meals()

        return self.async_show_form(
            step_id="class",
            data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
            errors=errors,
        )

    async def async_step_meals(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select meal types and create the entry."""
        if user_input is not None:
            school_name = str(self._school["SCHUL_NM"])
            return self.async_create_entry(
                title=f"{school_name} {self._grade}학년 {self._class_name}반",
                data={
                    CONF_OFFICE_CODE: self._office_code,
                    CONF_SCHOOL_CODE: str(self._school["SD_SCHUL_CODE"]),
                    CONF_SCHOOL_NAME: school_name,
                    CONF_SCHOOL_KIND: str(self._school["SCHUL_KND_SC_NM"]),
                    CONF_SCHOOL_HOMEPAGE: self._school.get("HMPG_ADRES"),
                },
                options={
                    CONF_API_KEY: self._api_key,
                    CONF_GRADE: self._grade,
                    CONF_CLASS_NAME: self._class_name,
                    CONF_MEAL_TYPES: list(user_input[CONF_MEAL_TYPES]),
                },
            )
        return self.async_show_form(
            step_id="meals",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MEAL_TYPES, default=DEFAULT_MEAL_TYPES
                    ): _meal_selector()
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return NeisSchoolOptionsFlow(config_entry)


class NeisSchoolOptionsFlow(config_entries.OptionsFlow):
    """Manage mutable NEIS School settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update credentials, profile, and meal types."""
        errors: dict[str, str] = {}
        current = self._entry.options
        if user_input is not None:
            api_key = str(user_input.get(CONF_API_KEY, "")).strip() or None
            api = NeisAPI(async_get_clientsession(self.hass), api_key)
            try:
                result = await api.get_classes(
                    str(self._entry.data[CONF_OFFICE_CODE]),
                    str(self._entry.data[CONF_SCHOOL_CODE]),
                    _academic_year(),
                    int(user_input[CONF_GRADE]),
                    str(user_input[CONF_CLASS_NAME]).strip(),
                )
            except NeisConnectionError:
                errors["base"] = "cannot_connect"
            except NeisApiError:
                errors["base"] = "api_error"
            else:
                if not result.rows:
                    errors["base"] = "class_not_found"
                elif not result.complete:
                    errors["base"] = "incomplete_data"
                else:
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_API_KEY: api_key,
                            CONF_GRADE: int(user_input[CONF_GRADE]),
                            CONF_CLASS_NAME: str(user_input[CONF_CLASS_NAME]).strip(),
                            CONF_MEAL_TYPES: list(user_input[CONF_MEAL_TYPES]),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_API_KEY, default=current.get(CONF_API_KEY) or ""
                ): _password_selector(),
                vol.Required(CONF_GRADE, default=current.get(CONF_GRADE, 1)): vol.All(
                    vol.Coerce(int), vol.Range(1, 6)
                ),
                vol.Required(
                    CONF_CLASS_NAME, default=current.get(CONF_CLASS_NAME, "1")
                ): str,
                vol.Required(
                    CONF_MEAL_TYPES,
                    default=current.get(CONF_MEAL_TYPES, DEFAULT_MEAL_TYPES),
                ): _meal_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
