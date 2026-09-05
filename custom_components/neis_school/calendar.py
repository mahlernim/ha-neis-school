"""Read-only NEIS school schedule calendar."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from time import monotonic

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeisSchoolConfigEntry
from .const import CONF_SCHOOL_NAME
from .coordinator import NeisSchoolCoordinator
from .entity import NeisSchoolEntity
from .helpers import applicable_schedule_rows, parse_neis_date
from .models import NeisResponse

CALENDAR_CACHE_SECONDS = 3 * 60 * 60
MAX_CALENDAR_CACHE_RANGES = 12


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeisSchoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the school schedule calendar."""
    coordinator = entry.runtime_data
    async_add_entities([NeisSchoolCalendar(coordinator)])


class NeisSchoolCalendar(NeisSchoolEntity, CalendarEntity):
    """Read-only, grade-filtered NEIS academic calendar."""

    _attr_translation_key = "school_calendar"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar"
        self._range_cache: dict[tuple[date, date], tuple[float, NeisResponse]] = {}

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
        start_day = start_date.date()
        inclusive_end = (end_date - timedelta(microseconds=1)).date()
        response = self._coordinator_response(start_day, inclusive_end)
        if response is None:
            cache_key = (start_day, inclusive_end)
            cached = self._range_cache.get(cache_key)
            if cached is not None and monotonic() - cached[0] < CALENDAR_CACHE_SECONDS:
                response = cached[1]
            else:
                response = await self.coordinator.api.get_schedule(
                    self.coordinator.office_code,
                    self.coordinator.school_code,
                    start_day,
                    inclusive_end,
                )
                if response.complete:
                    self._range_cache[cache_key] = (monotonic(), response)
                    if len(self._range_cache) > MAX_CALENDAR_CACHE_RANGES:
                        oldest = min(
                            self._range_cache,
                            key=lambda key: self._range_cache[key][0],
                        )
                        self._range_cache.pop(oldest)
        if not response.complete:
            return []
        return self._events_from_rows(response.rows, start_day, inclusive_end)

    def _coordinator_response(
        self, start_date: date, end_date: date
    ) -> NeisResponse | None:
        """Reuse the coordinator's complete lookahead whenever it covers the range."""
        data = self.coordinator.data
        if (
            data.upcoming_schedule.complete
            and start_date <= end_date
            and all(
                (response := data.schedules.get(start_date + timedelta(days=offset)))
                is not None
                and response.complete
                for offset in range((end_date - start_date).days + 1)
            )
        ):
            return data.upcoming_schedule
        return None

    def _events_from_rows(
        self,
        rows: tuple[dict, ...],
        lower_bound: date,
        upper_bound: date | None = None,
    ) -> list[CalendarEvent]:
        response = self.coordinator.data.upcoming_schedule
        filtered_response = type(response)(rows, len(rows), True, response.result_code)
        school_name = str(self.coordinator.entry.data[CONF_SCHOOL_NAME])
        events: list[CalendarEvent] = []
        for row in applicable_schedule_rows(filtered_response, self.coordinator.grade):
            event_date = parse_neis_date(str(row["AA_YMD"]))
            if event_date < lower_bound or (
                upper_bound is not None and event_date > upper_bound
            ):
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
