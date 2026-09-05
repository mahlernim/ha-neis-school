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


def _class_matches(
    row: dict[str, Any],
    office_code: str,
    school_code: str,
    academic_year: int,
    grade: int,
    class_name: str,
) -> bool:
    """Verify the requested class and any profile fields returned by NEIS."""
    expected = {
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "AY": str(academic_year),
        "GRADE": str(grade),
    }
    return (
        bool(class_name)
        and str(row.get("CLASS_NM") or "").strip() == class_name
        and all(
            field not in row or str(row[field]).strip() == value
            for field, value in expected.items()
        )
    )


class NeisSchoolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a NEIS School config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize transient flow state."""
        self._api_key: str | None = None
        self._api: NeisAPI | None = None
        self._office_code = ""
        self._school_query = ""
        self._schools: dict[str, dict[str, Any]] = {}
        self._school: dict[str, Any] = {}
        self._grade = 0
        self._class_name = ""
        self._class_choices: dict[str, str] = {}
        self._resume_step: str | None = None

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
                resume_step, self._resume_step = self._resume_step, None
                if resume_step == "class":
                    self._class_choices = {}
                    return await self.async_step_class()
                if resume_step == "school":
                    return await self.async_step_school(
                        {
                            CONF_OFFICE_CODE: self._office_code,
                            CONF_SCHOOL_NAME: self._school_query,
                        }
                    )
                return await self.async_step_school()

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    def _retry_credentials(self, resume_step: str, error: str) -> ConfigFlowResult:
        """Allow a key correction without discarding the user's setup progress."""
        self._resume_step = resume_step
        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
            errors={CONF_API_KEY if error == "invalid_auth" else "base": error},
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_school(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for a school."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._office_code = str(user_input[CONF_OFFICE_CODE])
            self._school_query = str(user_input[CONF_SCHOOL_NAME]).strip()
            if self._api is None:
                return self.async_abort(reason="unknown")
            if not self._school_query:
                return self._show_school_form({CONF_SCHOOL_NAME: "required"})
            try:
                result = await self._api.search_schools(
                    self._office_code, self._school_query
                )
            except NeisAuthenticationError:
                return self._retry_credentials("school", "invalid_auth")
            except NeisRateLimitError:
                errors["base"] = "rate_limited"
            except NeisApiError:
                errors["base"] = "api_error"
            except NeisConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not result.complete:
                    return self._show_school_form({"base": "incomplete_school_search"})
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

        return self._show_school_form(errors)

    def _show_school_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Preserve non-secret search fields when the user retries."""
        schema = vol.Schema(
            {
                vol.Required(CONF_OFFICE_CODE): vol.In(OFFICES),
                vol.Required(CONF_SCHOOL_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="school",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_OFFICE_CODE: self._office_code,
                    CONF_SCHOOL_NAME: self._school_query,
                },
            ),
            errors=errors,
        )

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
        self._class_choices = {}
        self._class_name = ""
        return await self.async_step_grade()

    def _profile_placeholders(self) -> dict[str, str]:
        """Keep school and academic-year context visible throughout setup."""
        return {
            "school_name": str(self._school.get("SCHUL_NM") or ""),
            "school_address": str(self._school.get("ORG_RDNMA") or ""),
            "academic_year": str(_academic_year()),
            "grade": str(self._grade),
            "class_name": self._class_name,
        }

    async def async_step_grade(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the student's grade."""
        if user_input is not None:
            self._grade = int(user_input[CONF_GRADE])
            self._class_choices = {}
            return await self.async_step_class()
        return self.async_show_form(
            step_id="grade",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GRADE, default=str(self._grade or 1)
                    ): _grade_schema(str(self._school["SCHUL_KND_SC_NM"]))
                }
            ),
            description_placeholders=self._profile_placeholders(),
        )

    async def async_step_class(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a class, retry its lookup, or correct the selected grade."""
        if self._api is None:
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            grade = int(user_input.get(CONF_GRADE, self._grade))
            if grade != self._grade:
                self._grade = grade
                self._class_name = ""
                self._class_choices = {}
                return await self.async_step_class()
            # A failed list lookup shows only the grade and can be retried as-is.
            if self._api.has_api_key and not self._class_choices:
                user_input = None
            else:
                self._class_name = str(user_input.get(CONF_CLASS_NAME, "")).strip()
                if not self._class_name:
                    return self._show_class_form({CONF_CLASS_NAME: "required"})

        if user_input is None and not self._api.has_api_key:
            return self._show_class_form(errors)
        try:
            result = await self._api.get_classes(
                self._office_code,
                str(self._school["SD_SCHUL_CODE"]),
                _academic_year(),
                self._grade,
                self._class_name if user_input is not None else None,
            )
        except NeisAuthenticationError:
            return self._retry_credentials("class", "invalid_auth")
        except NeisRateLimitError:
            errors["base"] = "rate_limited"
        except NeisConnectionError:
            errors["base"] = "cannot_connect"
        except NeisApiError:
            errors["base"] = "api_error"
        else:
            if not result.complete:
                if not self._api.has_api_key:
                    return self._retry_credentials("class", "incomplete_data")
                errors["base"] = "incomplete_data"
            elif user_input is None:
                self._class_choices = {
                    name: name
                    for row in result.rows
                    if (name := str(row.get("CLASS_NM") or "").strip())
                    and self._matches_class(row, name)
                }
                if not self._class_choices:
                    errors["base"] = "classes_unavailable"
            elif not any(
                self._matches_class(row, self._class_name) for row in result.rows
            ):
                errors[CONF_CLASS_NAME] = "class_not_found"
            else:
                return await self.async_step_meals()

        return self._show_class_form(errors)

    def _matches_class(self, row: dict[str, Any], class_name: str) -> bool:
        return _class_matches(
            row,
            self._office_code,
            str(self._school["SD_SCHUL_CODE"]),
            _academic_year(),
            self._grade,
            class_name,
        )

    def _show_class_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Retain valid class choices and allow grade correction on the same form."""
        schema = {
            vol.Required(CONF_GRADE, default=str(self._grade)): _grade_schema(
                str(self._school["SCHUL_KND_SC_NM"])
            )
        }
        if self._class_choices:
            field = vol.Optional(CONF_CLASS_NAME)
            if self._class_name in self._class_choices:
                field = vol.Optional(CONF_CLASS_NAME, default=self._class_name)
            schema[field] = vol.In(self._class_choices)
        elif self._api is not None and not self._api.has_api_key:
            schema[vol.Optional(CONF_CLASS_NAME)] = str
        return self.async_show_form(
            step_id="class",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema),
                {CONF_CLASS_NAME: self._class_name}
                if self._class_name
                and (not self._class_choices or self._class_name in self._class_choices)
                else {},
            ),
            errors=errors,
            description_placeholders=self._profile_placeholders(),
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
            step_id="meals" if self._api and self._api.has_api_key else "meals_limited",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MEAL_TYPES, default=DEFAULT_MEAL_TYPES
                    ): _meal_schema()
                }
            ),
            description_placeholders=self._profile_placeholders(),
        )

    async def async_step_meals_limited(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use localized limited-mode guidance on the same final setup form."""
        return await self.async_step_meals(user_input)

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
            class_name = str(user_input[CONF_CLASS_NAME]).strip()
            if not class_name:
                return self._show_options_form(
                    user_input, {CONF_CLASS_NAME: "required"}
                )
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
                if not result.complete:
                    errors["base"] = "incomplete_data"
                elif not any(
                    _class_matches(
                        row,
                        str(self.config_entry.data[CONF_OFFICE_CODE]),
                        str(self.config_entry.data[CONF_SCHOOL_CODE]),
                        _academic_year(),
                        int(user_input[CONF_GRADE]),
                        class_name,
                    )
                    for row in result.rows
                ):
                    errors[CONF_CLASS_NAME] = "class_not_found"
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
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "school_name": str(self.config_entry.data[CONF_SCHOOL_NAME]),
                "academic_year": str(_academic_year()),
            },
        )
