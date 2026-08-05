"""Binary sensors for NEIS School."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NeisSchoolCoordinator
from .entity import NeisSchoolEntity
from .helpers import evaluate_schoolday


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up schoolday binary sensors."""
    coordinator: NeisSchoolCoordinator = entry.runtime_data
    async_add_entities(
        [
            NeisSchooldayBinarySensor(coordinator, 0),
            NeisSchooldayBinarySensor(coordinator, 1),
        ]
    )


class NeisSchooldayBinarySensor(NeisSchoolEntity, BinarySensorEntity):
    """Whether the selected student goes to school."""

    _unrecorded_attributes = frozenset({"events"})

    def __init__(self, coordinator: NeisSchoolCoordinator, day_offset: int) -> None:
        super().__init__(coordinator)
        self._day_offset = day_offset
        day_key = "today" if day_offset == 0 else "tomorrow"
        self._attr_translation_key = f"schoolday_{day_key}"
        self._attr_unique_id = f"{coordinator.school_code}_schoolday_{day_key}"

    @property
    def available(self) -> bool:
        return super().available and self._result.available

    @property
    def is_on(self) -> bool | None:
        return self._result.is_schoolday

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._result
        return {
            "date": self._target_date.isoformat(),
            "reason": result.reason,
            "events": list(result.events),
            "grade": self.coordinator.grade,
            "class": self.coordinator.class_name,
            "api_mode": "full" if self.coordinator.api.has_api_key else "limited",
        }

    @property
    def _target_date(self) -> date:
        return self.coordinator.data.local_date + timedelta(days=self._day_offset)

    @property
    def _result(self):
        return evaluate_schoolday(
            self._target_date,
            self.coordinator.data.schedules[self._target_date],
            self.coordinator.grade,
        )
