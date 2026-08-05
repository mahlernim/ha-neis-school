"""Read-only NEIS school schedule calendar."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SCHOOL_NAME
from .coordinator import NeisSchoolCoordinator
from .entity import NeisSchoolEntity
from .helpers import applicable_schedule_rows, parse_neis_date


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the school schedule calendar."""
    coordinator: NeisSchoolCoordinator = entry.runtime_data
    async_add_entities([NeisSchoolCalendar(coordinator)])


class NeisSchoolCalendar(NeisSchoolEntity, CalendarEntity):
    """Read-only, grade-filtered NEIS academic calendar."""

    _attr_translation_key = "school_calendar"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_calendar"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.api.has_api_key
            and self.coordinator.data.upcoming_schedule.complete
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next event from cached data."""
        events = self._events_from_rows(
            self.coordinator.data.upcoming_schedule.rows,
            self.coordinator.data.local_date,
        )
        return events[0] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events in the requested range."""
        if not self.coordinator.api.has_api_key or end_date <= start_date:
            return []
        inclusive_end = (end_date - timedelta(microseconds=1)).date()
        response = await self.coordinator.api.get_schedule(
            self.coordinator.office_code,
            self.coordinator.school_code,
            start_date.date(),
            inclusive_end,
        )
        if not response.complete:
            return []
        return self._events_from_rows(response.rows, start_date.date())

    def _events_from_rows(
        self, rows: tuple[dict, ...], lower_bound: date
    ) -> list[CalendarEvent]:
        response = self.coordinator.data.upcoming_schedule
        filtered_response = type(response)(rows, len(rows), True, response.result_code)
        school_name = str(self.coordinator.entry.data[CONF_SCHOOL_NAME])
        events: list[CalendarEvent] = []
        for row in applicable_schedule_rows(filtered_response, self.coordinator.grade):
            event_date = parse_neis_date(str(row["AA_YMD"]))
            if event_date < lower_bound:
                continue
            summary = str(row.get("EVENT_NM", "")).strip()
            if not summary:
                continue
            events.append(
                CalendarEvent(
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    summary=summary,
                    description=str(row.get("EVENT_CNTNT", "")) or None,
                    location=school_name,
                )
            )
        return sorted(events, key=lambda item: (item.start, item.summary))
