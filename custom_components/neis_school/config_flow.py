"""Config flow for NEIS School."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    NeisAPI,
    NeisApiError,
    NeisAuthenticationError,
    NeisConnectionError,
    NeisRateLimitError,
)
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
    current = today or dt_util.now().date()
    return current.year if current.month >= 3 else current.year - 1


def _password_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


def _credentials_schema() -> vol.Schema:
    """Return the credential form shared by setup and reauthentication."""
    return vol.Schema(
        {
            vol.Optional(CONF_API_KEY): _password_selector(),
            vol.Optional(CONF_LIMITED_ACK, default=False): bool,
        }
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


def _meal_schema() -> vol.Schema:
    """Require at least one enabled meal type."""
    return vol.All(_meal_selector(), vol.Length(min=1))


def _grade_schema(school_kind: str) -> vol.Schema:
    """Return a grade dropdown restricted to the school type."""
    maximum = 3 if school_kind in {"중학교", "고등학교"} else 6
    return vol.All(
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[str(grade) for grade in range(1, maximum + 1)],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Coerce(int),
        vol.Range(min=1, max=maximum),
    )


def _profile_is_configured(
    hass: HomeAssistant,
    office_code: str,
    school_code: str,
    grade: int,
    class_name: str,
    *,
    exclude_entry_id: str | None = None,
) -> bool:
    """Return whether the same school profile already has an entry."""
    normalized_class = class_name.strip()
    return any(
        entry.entry_id != exclude_entry_id
        and str(entry.data.get(CONF_OFFICE_CODE)) == office_code
        and str(entry.data.get(CONF_SCHOOL_CODE)) == school_code
        and int(entry.options.get(CONF_GRADE, 0)) == grade
        and str(entry.options.get(CONF_CLASS_NAME, "")).strip() == normalized_class
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class NeisSchoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a NEIS School config flow."""

    VERSION = 2

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
    ) -> ConfigFlowResult:
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

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_school(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for a school."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._office_code = str(user_input[CONF_OFFICE_CODE])
            if self._api is None:
                return self.async_abort(reason="unknown")
            try:
                result = await self._api.search_schools(
                    self._office_code, str(user_input[CONF_SCHOOL_NAME]).strip()
                )
            except NeisAuthenticationError:
                errors["base"] = "invalid_auth"
            except NeisRateLimitError:
                errors["base"] = "rate_limited"
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
    ) -> ConfigFlowResult:
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

    async def _after_school_selected(self) -> ConfigFlowResult:
        """Continue with the student profile after selecting a school."""
        return await self.async_step_grade()

    async def async_step_grade(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the student's grade."""
        if user_input is not None:
            self._grade = int(user_input[CONF_GRADE])
            return await self.async_step_class()
        return self.async_show_form(
            step_id="grade",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GRADE): _grade_schema(
                        str(self._school["SCHUL_KND_SC_NM"])
                    )
                }
            ),
        )

    async def async_step_class(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose or enter a class and validate it."""
        errors: dict[str, str] = {}
        if self._api is None:
            return self.async_abort(reason="unknown")
        if user_input is None and self._api.has_api_key:
            try:
                result = await self._api.get_classes(
                    self._office_code,
                    str(self._school["SD_SCHUL_CODE"]),
                    _academic_year(),
                    self._grade,
                )
            except NeisAuthenticationError:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
                    errors={"base": "invalid_auth"},
                )
            except NeisRateLimitError:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
                    errors={"base": "rate_limited"},
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
            if not result.complete:
                return self.async_show_form(
                    step_id="class",
                    data_schema=vol.Schema({vol.Required(CONF_CLASS_NAME): str}),
                    errors={"base": "incomplete_data"},
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
            except NeisAuthenticationError:
                errors["base"] = "invalid_auth"
            except NeisRateLimitError:
                errors["base"] = "rate_limited"
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
    ) -> ConfigFlowResult:
        """Select meal types and create the entry."""
        if user_input is not None:
            school_name = str(self._school["SCHUL_NM"])
            school_code = str(self._school["SD_SCHUL_CODE"])
            if _profile_is_configured(
                self.hass,
                self._office_code,
                school_code,
                self._grade,
                self._class_name,
            ):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=f"{school_name} {self._grade}학년 {self._class_name}반",
                data={
                    CONF_OFFICE_CODE: self._office_code,
                    CONF_SCHOOL_CODE: school_code,
                    CONF_SCHOOL_NAME: school_name,
                    CONF_SCHOOL_KIND: str(self._school["SCHUL_KND_SC_NM"]),
                    CONF_SCHOOL_HOMEPAGE: self._school.get("HMPG_ADRES"),
                    CONF_API_KEY: self._api_key,
                },
                options={
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
                    ): _meal_schema()
                }
            ),
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after NEIS rejects the configured key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace an invalid key or explicitly switch to limited mode."""
        return await self._async_credentials_update(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow proactive API credential changes."""
        return await self._async_credentials_update(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def _async_credentials_update(
        self,
        step_id: str,
        entry: config_entries.ConfigEntry,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate and store credentials in config entry data."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.get(CONF_API_KEY, "")).strip() or None
            if not api_key and not user_input.get(CONF_LIMITED_ACK, False):
                errors["base"] = "limited_not_acknowledged"
            elif api_key:
                api = NeisAPI(async_get_clientsession(self.hass), api_key)
                try:
                    await api.search_schools(
                        str(entry.data[CONF_OFFICE_CODE]),
                        str(entry.data[CONF_SCHOOL_NAME]),
                    )
                except NeisAuthenticationError:
                    errors["base"] = "invalid_auth"
                except NeisRateLimitError:
                    errors["base"] = "rate_limited"
                except NeisConnectionError:
                    errors["base"] = "cannot_connect"
                except NeisApiError:
                    errors["base"] = "api_error"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=_credentials_schema(),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return NeisSchoolOptionsFlow()


class NeisSchoolOptionsFlow(config_entries.OptionsFlow):
    """Manage mutable NEIS School settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the student profile and meal types."""
        errors: dict[str, str] = {}
        current = self.config_entry.options
        if user_input is not None:
            api_key = self.config_entry.data.get(
                CONF_API_KEY, current.get(CONF_API_KEY)
            )
            api = NeisAPI(async_get_clientsession(self.hass), api_key)
            try:
                result = await api.get_classes(
                    str(self.config_entry.data[CONF_OFFICE_CODE]),
                    str(self.config_entry.data[CONF_SCHOOL_CODE]),
                    _academic_year(),
                    int(user_input[CONF_GRADE]),
                    str(user_input[CONF_CLASS_NAME]).strip(),
                )
            except NeisAuthenticationError:
                errors["base"] = "invalid_auth"
            except NeisRateLimitError:
                errors["base"] = "rate_limited"
            except NeisConnectionError:
                errors["base"] = "cannot_connect"
            except NeisApiError:
                errors["base"] = "api_error"
            else:
                if not result.rows:
                    errors["base"] = "class_not_found"
                elif not result.complete:
                    errors["base"] = "incomplete_data"
                elif _profile_is_configured(
                    self.hass,
                    str(self.config_entry.data[CONF_OFFICE_CODE]),
                    str(self.config_entry.data[CONF_SCHOOL_CODE]),
                    int(user_input[CONF_GRADE]),
                    str(user_input[CONF_CLASS_NAME]),
                    exclude_entry_id=self.config_entry.entry_id,
                ):
                    errors["base"] = "already_configured"
                else:
                    grade = int(user_input[CONF_GRADE])
                    class_name = str(user_input[CONF_CLASS_NAME]).strip()
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        title=(
                            f"{self.config_entry.data[CONF_SCHOOL_NAME]} "
                            f"{grade}학년 {class_name}반"
                        ),
                    )
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_GRADE: grade,
                            CONF_CLASS_NAME: class_name,
                            CONF_MEAL_TYPES: list(user_input[CONF_MEAL_TYPES]),
                        },
                    )

        return self._show_options_form(user_input, errors)

    def _show_options_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> ConfigFlowResult:
        """Show the options form with safe defaults."""
        current = self.config_entry.options
        defaults = user_input or current
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GRADE, default=str(defaults.get(CONF_GRADE, 1))
                ): _grade_schema(str(self.config_entry.data[CONF_SCHOOL_KIND])),
                vol.Required(
                    CONF_CLASS_NAME, default=defaults.get(CONF_CLASS_NAME, "1")
                ): str,
                vol.Required(
                    CONF_MEAL_TYPES,
                    default=defaults.get(CONF_MEAL_TYPES, DEFAULT_MEAL_TYPES),
                ): _meal_schema(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
