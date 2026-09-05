"""Data coordinator for NEIS School."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NeisAPI, NeisAuthenticationError, NeisError
from .const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_KIND,
    DOMAIN,
    ISSUE_INCOMPLETE_DATA,
    RETRY_DELAYS,
    SCHEDULE_LOOKAHEAD_DAYS,
    SNAPSHOT_DAYS,
)
from .models import NeisCoordinatorData, NeisResponse

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1


class NeisSchoolCoordinator(DataUpdateCoordinator[NeisCoordinatorData]):
    """Fetch data shared by all entities for one school."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: NeisAPI,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api = api
        self.office_code = str(entry.data[CONF_OFFICE_CODE])
        self.school_code = str(entry.data[CONF_SCHOOL_CODE])
        self.school_kind = str(entry.data[CONF_SCHOOL_KIND])
        self.grade = int(entry.options[CONF_GRADE])
        self.class_name = str(entry.options[CONF_CLASS_NAME])
        self.last_attempt = None
        self.last_error: str | None = None
        self.consecutive_failures = 0
        self.using_cached_data = False
        self._cancel_retry: Callable[[], None] | None = None
        self.store: Store[dict] = Store(
            hass, _STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.snapshot"
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )

    async def async_initialize(self) -> None:
        """Restore a usable snapshot, then refresh without blocking startup."""
        stored = await self.store.async_load()
        if (
            isinstance(stored, dict)
            and stored.get("profile") == self._snapshot_profile()
        ):
            try:
                cached = NeisCoordinatorData.from_dict(stored["snapshot"])
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Ignoring invalid NEIS snapshot: %s", err)
            else:
                today = dt_util.now().date()
                if self._covers_required_dates(cached, today):
                    self.using_cached_data = True
                    self.async_set_updated_data(replace(cached, local_date=today))
                    self.hass.async_create_task(self.async_request_refresh())
                    return
        await self.async_config_entry_first_refresh()

    async def async_project_date(self, target: date) -> None:
        """Project cached date-indexed data without requiring a network call."""
        if self.data is not None and self._covers_required_dates(self.data, target):
            self.async_set_updated_data(replace(self.data, local_date=target))
        else:
            await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        """Cancel recovery and let Home Assistant stop pending refreshes."""
        self._cancel_recovery_retry()
        await super().async_shutdown()

    def _cancel_recovery_retry(self) -> None:
        """Cancel the recovery timer without disabling future updates."""
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    def _snapshot_profile(self) -> dict[str, str | int]:
        """Identify the snapshot's school, student profile, and API mode."""
        return {
            CONF_OFFICE_CODE: self.office_code,
            CONF_SCHOOL_CODE: self.school_code,
            CONF_SCHOOL_KIND: self.school_kind,
            CONF_GRADE: self.grade,
            CONF_CLASS_NAME: self.class_name,
            "api_mode": "full" if self.api.has_api_key else "limited",
        }

    async def _async_save_snapshot(self, data: NeisCoordinatorData) -> None:
        """Store data with its profile so options changes cannot reuse old lessons."""
        await self.store.async_save(
            {"profile": self._snapshot_profile(), "snapshot": data.as_dict()}
        )

    async def _async_update_data(self) -> NeisCoordinatorData:
        """Fetch meals, schedules, and timetables."""
        today = dt_util.now().date()
        if not self.api.has_api_key:
            return await self._async_update_limited(today)
        snapshot_end = today + timedelta(days=SNAPSHOT_DAYS - 1)
        schedule_end = today + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS)
        self.last_attempt = dt_util.utcnow()
        results = await asyncio.gather(
            self.api.get_meals_range(
                self.office_code, self.school_code, today, snapshot_end
            ),
            self.api.get_schedule(
                self.office_code, self.school_code, today, schedule_end
            ),
            self.api.get_timetable_range(
                self.office_code,
                self.school_code,
                self.school_kind,
                today,
                snapshot_end,
                self.grade,
                self.class_name,
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, NeisAuthenticationError):
                self._record_failure(result)
                self._cancel_recovery_retry()
                raise ConfigEntryAuthFailed(
                    "NEIS API key is invalid or restricted"
                ) from result
            if isinstance(result, BaseException) and not isinstance(result, NeisError):
                raise result

        failures = [result for result in results if isinstance(result, NeisError)]
        if failures:
            self._record_failure(failures[0])
            self._schedule_retry()

        previous = self.data
        meals_result, schedule_result, timetable_result = results
        meals = self._source_or_cached(
            "meals",
            meals_result,
            previous.meals if previous else None,
            today,
            snapshot_end,
            "MLSV_YMD",
        )
        schedules = self._source_or_cached(
            "schedules",
            schedule_result,
            previous.schedules if previous else None,
            today,
            schedule_end,
            "AA_YMD",
        )
        timetables = self._source_or_cached(
            "timetables",
            timetable_result,
            previous.timetables if previous else None,
            today,
            snapshot_end,
            "ALL_TI_YMD",
        )
        if meals is None or schedules is None or timetables is None:
            raise UpdateFailed("Unable to update NEIS school data") from failures[0]

        if isinstance(schedule_result, NeisResponse):
            upcoming_schedule = schedule_result
        elif previous is not None and previous.upcoming_schedule.complete:
            upcoming_schedule = previous.upcoming_schedule
        else:
            raise UpdateFailed("Unable to update NEIS school data") from failures[0]

        sources = set()
        for name, response in (
            ("meals", meals_result),
            ("schedules", schedule_result),
            ("timetables", timetable_result),
        ):
            if isinstance(response, NeisError) or (
                isinstance(response, NeisResponse)
                and not response.complete
                and response.result_code != "LIMITED_MODE"
            ):
                sources.add(name)
        self._update_incomplete_issue(sources)
        completed_at = dt_util.utcnow()
        if not failures:
            self.last_attempt = completed_at
            self.last_error = None
            self.consecutive_failures = 0
            self.using_cached_data = False
            self._cancel_recovery_retry()
        else:
            self.using_cached_data = True
        data = NeisCoordinatorData(
            local_date=today,
            meals=meals,
            schedules=schedules,
            timetables=timetables,
            upcoming_schedule=upcoming_schedule,
            last_success=(completed_at if not failures else previous.last_success),
            last_attempt=completed_at,
            incomplete_sources=sources,
        )
        await self._async_save_snapshot(data)
        return data

    async def _async_update_limited(self, today: date) -> NeisCoordinatorData:
        """Preserve exact today/tomorrow queries for anonymous limited mode."""
        tomorrow = today + timedelta(days=1)
        self.last_attempt = dt_util.utcnow()
        results = await asyncio.gather(
            self.api.get_meals(self.office_code, self.school_code, today),
            self.api.get_meals(self.office_code, self.school_code, tomorrow),
            self.api.get_schedule(self.office_code, self.school_code, today, today),
            self.api.get_schedule(
                self.office_code, self.school_code, tomorrow, tomorrow
            ),
            self.api.get_timetable(
                self.office_code,
                self.school_code,
                self.school_kind,
                today,
                self.grade,
                self.class_name,
            ),
            self.api.get_timetable(
                self.office_code,
                self.school_code,
                self.school_kind,
                tomorrow,
                self.grade,
                self.class_name,
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, NeisError):
                raise result
        failures = [result for result in results if isinstance(result, NeisError)]
        previous = self.data
        if failures:
            self._record_failure(failures[0])
            self._schedule_retry()
            if previous is None or not self._covers_required_dates(previous, today):
                raise UpdateFailed("Unable to update NEIS school data") from failures[0]
            self.using_cached_data = True
            data = replace(
                previous,
                local_date=today,
                last_attempt=dt_util.utcnow(),
                incomplete_sources={"limited_mode_refresh"},
            )
            await self._async_save_snapshot(data)
            return data

        (
            meals_today,
            meals_tomorrow,
            schedule_today,
            schedule_tomorrow,
            timetable_today,
            timetable_tomorrow,
        ) = results
        responses = {
            "meals_today": meals_today,
            "meals_tomorrow": meals_tomorrow,
            "schedule_today": schedule_today,
            "schedule_tomorrow": schedule_tomorrow,
            "timetable_today": timetable_today,
            "timetable_tomorrow": timetable_tomorrow,
        }
        sources = {
            name
            for name, response in responses.items()
            if isinstance(response, NeisResponse) and not response.complete
        }
        self._update_incomplete_issue(sources)
        completed_at = dt_util.utcnow()
        self.last_attempt = completed_at
        self.last_error = None
        self.consecutive_failures = 0
        self.using_cached_data = False
        self._cancel_recovery_retry()
        data = NeisCoordinatorData(
            local_date=today,
            meals={today: meals_today, tomorrow: meals_tomorrow},
            schedules={today: schedule_today, tomorrow: schedule_tomorrow},
            timetables={today: timetable_today, tomorrow: timetable_tomorrow},
            upcoming_schedule=NeisResponse.limited(),
            last_success=completed_at,
            last_attempt=completed_at,
            incomplete_sources=sources,
        )
        await self._async_save_snapshot(data)
        return data

    def _source_or_cached(
        self,
        name: str,
        result: NeisResponse | BaseException,
        cached: dict[date, NeisResponse] | None,
        start: date,
        end: date,
        date_field: str,
    ) -> dict[date, NeisResponse] | None:
        """Split a range response or retain a complete cached date range."""
        if isinstance(result, NeisResponse):
            return self._split_by_date(result, start, end, date_field)
        required = (start, start + timedelta(days=1))
        if cached is not None and all(day in cached for day in required):
            _LOGGER.warning("NEIS %s refresh failed; retaining cached data", name)
            return {day: response for day, response in cached.items() if day >= start}
        return None

    @staticmethod
    def _split_by_date(
        response: NeisResponse, start: date, end: date, date_field: str
    ) -> dict[date, NeisResponse]:
        """Split a complete range response into complete per-date responses."""
        values: dict[date, NeisResponse] = {}
        for day in NeisSchoolCoordinator._date_range(start, end):
            key = day.strftime("%Y%m%d")
            rows = tuple(
                row for row in response.rows if str(row.get(date_field, "")) == key
            )
            values[day] = NeisResponse(
                rows, len(rows), response.complete, response.result_code
            )
        return values

    @staticmethod
    def _date_range(start: date, end: date) -> tuple[date, ...]:
        return tuple(
            start + timedelta(days=offset) for offset in range((end - start).days + 1)
        )

    @staticmethod
    def _covers_required_dates(data: NeisCoordinatorData, target: date) -> bool:
        tomorrow = target + timedelta(days=1)
        return all(
            day in values
            for values in (data.meals, data.schedules, data.timetables)
            for day in (target, tomorrow)
        )

    def _schedule_retry(self) -> None:
        self._cancel_recovery_retry()
        if self._shutdown_requested:
            return
        delay = RETRY_DELAYS[min(self.consecutive_failures - 1, len(RETRY_DELAYS) - 1)]

        def _retry(_now) -> None:
            self._cancel_retry = None
            self.hass.async_create_task(self.async_request_refresh())

        self._cancel_retry = async_call_later(self.hass, delay, _retry)

    def _record_failure(self, err: NeisError) -> None:
        """Record a sanitized failed refresh for diagnostics."""
        self.last_attempt = dt_util.utcnow()
        self.last_error = type(err).__name__
        self.consecutive_failures += 1
        _LOGGER.warning("NEIS update failed (%s)", self.last_error)

    def _update_incomplete_issue(self, sources: set[str]) -> None:
        """Create or clear the limited-data repair issue."""
        issue_id = f"{ISSUE_INCOMPLETE_DATA}_{self.entry.entry_id}"
        if sources:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_INCOMPLETE_DATA,
                translation_placeholders={
                    "sources": ", ".join(sorted(sources)),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def clear_incomplete_issue(self) -> None:
        """Remove the entry-scoped repair issue when the entry unloads."""
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            f"{ISSUE_INCOMPLETE_DATA}_{self.entry.entry_id}",
        )

    def configured_api_key(self) -> str | None:
        """Return the current credential without exposing it elsewhere."""
        value = self.entry.data.get(CONF_API_KEY, self.entry.options.get(CONF_API_KEY))
        return str(value) if value else None
