"""Data coordinator for NEIS School."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NeisAPI, NeisError
from .const import (
    CONF_API_KEY,
    CONF_CLASS_NAME,
    CONF_GRADE,
    CONF_OFFICE_CODE,
    CONF_SCHOOL_CODE,
    CONF_SCHOOL_KIND,
    DOMAIN,
    ISSUE_INCOMPLETE_DATA,
    SCHEDULE_LOOKAHEAD_DAYS,
    UPDATE_INTERVAL,
)
from .models import NeisCoordinatorData, NeisResponse

_LOGGER = logging.getLogger(__name__)


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
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> NeisCoordinatorData:
        """Fetch meals, schedules, and timetables."""
        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)
        try:
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
                self._async_upcoming_schedule(today),
            )
        except NeisError as err:
            if self.data is not None and self.data.local_date == today:
                self.data.last_attempt = dt_util.utcnow()
                self.data.last_error = type(err).__name__
                self.data.retained_after_error = True
                _LOGGER.warning(
                    "NEIS update failed (%s), preserving today's prior data",
                    type(err).__name__,
                )
                return self.data
            raise UpdateFailed("Unable to update NEIS school data") from err

        (
            meals_today,
            meals_tomorrow,
            schedule_today,
            schedule_tomorrow,
            timetable_today,
            timetable_tomorrow,
            upcoming_schedule,
        ) = results
        sources = {
            name
            for name, response in (
                ("meals_today", meals_today),
                ("meals_tomorrow", meals_tomorrow),
                ("schedule_today", schedule_today),
                ("schedule_tomorrow", schedule_tomorrow),
                ("timetable_today", timetable_today),
                ("timetable_tomorrow", timetable_tomorrow),
                ("upcoming_schedule", upcoming_schedule),
            )
            if not response.complete and response.result_code != "LIMITED_MODE"
        }
        self._update_incomplete_issue(sources)
        completed_at = dt_util.utcnow()
        return NeisCoordinatorData(
            local_date=today,
            meals={today: meals_today, tomorrow: meals_tomorrow},
            schedules={today: schedule_today, tomorrow: schedule_tomorrow},
            timetables={today: timetable_today, tomorrow: timetable_tomorrow},
            upcoming_schedule=upcoming_schedule,
            last_success=completed_at,
            last_attempt=completed_at,
            incomplete_sources=sources,
        )

    async def _async_upcoming_schedule(self, today) -> NeisResponse:
        """Fetch complete lookahead data only in authenticated mode."""
        if not self.api.has_api_key:
            return NeisResponse.limited()
        return await self.api.get_schedule(
            self.office_code,
            self.school_code,
            today,
            today + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS),
        )

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

    def configured_api_key(self) -> str | None:
        """Return the current credential without exposing it elsewhere."""
        value = self.entry.options.get(CONF_API_KEY)
        return str(value) if value else None
