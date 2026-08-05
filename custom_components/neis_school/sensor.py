"""Sensor entities for NEIS School."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_MEAL_TYPES,
    CONF_SCHOOL_NAME,
    MEAL_BREAKFAST,
    MEAL_DINNER,
    MEAL_LUNCH,
    SCHEDULE_LOOKAHEAD_DAYS,
)
from .coordinator import NeisSchoolCoordinator
from .entity import NeisSchoolEntity
from .helpers import (
    applicable_schedule_rows,
    clean_menu,
    evaluate_schoolday,
    format_meal_tts,
    format_timetable,
    next_schoolday,
    parse_allergens,
    parse_calories,
    parse_label_values,
    parse_neis_date,
    parse_origin_lines,
)

_MEAL_KEYS = {
    MEAL_BREAKFAST: "breakfast",
    MEAL_LUNCH: "lunch",
    MEAL_DINNER: "dinner",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NEIS School sensors."""
    coordinator: NeisSchoolCoordinator = entry.runtime_data
    meal_types = entry.options.get(CONF_MEAL_TYPES, [MEAL_LUNCH])
    entities: list[SensorEntity] = []
    for meal_type in meal_types:
        entities.extend(
            (
                NeisMealSensor(coordinator, str(meal_type), 0),
                NeisMealSensor(coordinator, str(meal_type), 1),
            )
        )
    entities.extend(
        (
            NeisScheduleTodaySensor(coordinator),
            NeisNextEventSensor(coordinator),
            NeisNextSchooldaySensor(coordinator),
            NeisTimetableSensor(coordinator, 0),
            NeisTimetableSensor(coordinator, 1),
            NeisApiModeSensor(coordinator),
            NeisLastUpdateSensor(coordinator),
        )
    )
    async_add_entities(entities)


class NeisMealSensor(NeisSchoolEntity, SensorEntity):
    """A breakfast, lunch, or dinner sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["available", "no_meal"]
    _unrecorded_attributes = frozenset(
        {"menu", "menu_tts", "nutrition", "origins", "allergens"}
    )

    def __init__(
        self, coordinator: NeisSchoolCoordinator, meal_type: str, day_offset: int
    ) -> None:
        super().__init__(coordinator)
        self._meal_type = meal_type
        self._day_offset = day_offset
        day_key = "today" if day_offset == 0 else "tomorrow"
        meal_key = _MEAL_KEYS[meal_type]
        self._attr_translation_key = f"{meal_key}_{day_key}"
        self._attr_unique_id = f"{coordinator.school_code}_{meal_key}_{day_key}"

    @property
    def available(self) -> bool:
        """Return whether this response is complete."""
        response = self.coordinator.data.meals.get(self._target_date)
        return super().available and response is not None and response.complete

    @property
    def native_value(self) -> str:
        """Return meal availability."""
        return "available" if self._row is not None else "no_meal"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return meal details."""
        row = self._row
        school_name = str(self.coordinator.entry.data.get(CONF_SCHOOL_NAME) or "")
        meal_name = {
            MEAL_BREAKFAST: "조식",
            MEAL_LUNCH: "중식",
            MEAL_DINNER: "석식",
        }[self._meal_type]
        attributes: dict[str, Any] = {
            "date": self._target_date.isoformat(),
            "api_mode": "full" if self.coordinator.api.has_api_key else "limited",
            "data_complete": self.available,
            "menu": "",
            "menu_tts": format_meal_tts(
                self._target_date, school_name, meal_name, ""
            ),
        }
        if row is None:
            return attributes
        raw_menu = str(row.get("DDISH_NM", ""))
        menu = clean_menu(raw_menu)
        school_name = str(row.get("SCHUL_NM") or school_name)
        meal_name = str(row.get("MMEAL_SC_NM") or meal_name)
        menu_tts = format_meal_tts(
            self._target_date, school_name, meal_name, menu
        )
        attributes.update(
            {
                "menu": menu,
                "menu_tts": menu_tts,
                "calories_kcal": parse_calories(row.get("CAL_INFO")),
                "nutrition": parse_label_values(row.get("NTR_INFO")),
                "allergens": parse_allergens(raw_menu),
                "origins": parse_origin_lines(row.get("ORPLC_INFO")),
                "serving_count": row.get("MLSV_FGR"),
                "loaded_at": row.get("LOAD_DTM"),
            }
        )
        return attributes

    @property
    def _target_date(self) -> date:
        return self.coordinator.data.local_date + timedelta(days=self._day_offset)

    @property
    def _row(self) -> dict[str, Any] | None:
        response = self.coordinator.data.meals.get(self._target_date)
        if response is None:
            return None
        return next(
            (
                row
                for row in response.rows
                if str(row.get("MMEAL_SC_CODE")) == self._meal_type
            ),
            None,
        )


class NeisScheduleTodaySensor(NeisSchoolEntity, SensorEntity):
    """Today's applicable school schedule."""

    _attr_translation_key = "schedule_today"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["scheduled", "none"]
    _unrecorded_attributes = frozenset(
        {"events", "schedule_text", "schedule_tts"}
    )

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_schedule_today"

    @property
    def available(self) -> bool:
        response = self.coordinator.data.schedules.get(self.coordinator.data.local_date)
        return super().available and response is not None and response.complete

    @property
    def native_value(self) -> str:
        return "scheduled" if self._event_names else "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        response = self.coordinator.data.schedules[self.coordinator.data.local_date]
        rows = applicable_schedule_rows(response, self.coordinator.grade)
        schedule_text, schedule_tts = _format_schedule_for_tts(
            self.coordinator.data.local_date,
            str(self.coordinator.entry.data[CONF_SCHOOL_NAME]),
            self._event_names,
        )
        return {
            "date": self.coordinator.data.local_date.isoformat(),
            "events": [
                {
                    "name": row.get("EVENT_NM"),
                    "description": row.get("EVENT_CNTNT"),
                    "day_type": row.get("SBTR_DD_SC_NM"),
                }
                for row in rows
            ],
            "schedule_text": schedule_text,
            "schedule_tts": schedule_tts,
            "data_complete": response.complete,
        }

    @property
    def _event_names(self) -> list[str]:
        """Return non-empty applicable event names."""
        rows = applicable_schedule_rows(
            self.coordinator.data.schedules[self.coordinator.data.local_date],
            self.coordinator.grade,
        )
        return [
            name
            for row in rows
            if (name := str(row.get("EVENT_NM", "")).strip())
        ]


def _format_schedule_for_tts(
    target_date: date, school_name: str, event_names: list[str]
) -> tuple[str, str]:
    """Return display and Korean TTS text for one day's schedule."""
    schedule_text = ", ".join(event_names)
    date_text = f"{target_date.month}월 {target_date.day}일"
    if schedule_text:
        return (
            schedule_text,
            f"{date_text} {school_name} 학사일정은 {schedule_text}입니다.",
        )
    return "", f"{date_text} {school_name}에 등록된 학사일정은 없습니다."


class NeisNextEventSensor(NeisSchoolEntity, SensorEntity):
    """Date of the next applicable school event."""

    _attr_translation_key = "next_school_event"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_next_school_event"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.upcoming_schedule.complete
            and self._next_row is not None
        )

    @property
    def native_value(self) -> date | None:
        row = self._next_row
        return parse_neis_date(str(row["AA_YMD"])) if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        row = self._next_row
        if row is None:
            return {}
        event_date = parse_neis_date(str(row["AA_YMD"]))
        return {
            "event": row.get("EVENT_NM"),
            "description": row.get("EVENT_CNTNT"),
            "days_remaining": (event_date - self.coordinator.data.local_date).days,
        }

    @property
    def _next_row(self) -> dict[str, Any] | None:
        rows = applicable_schedule_rows(
            self.coordinator.data.upcoming_schedule, self.coordinator.grade
        )
        rows = tuple(
            row
            for row in rows
            if str(row.get("EVENT_NM", "")).strip()
            and parse_neis_date(str(row["AA_YMD"])) >= self.coordinator.data.local_date
        )
        return min(rows, key=lambda row: str(row["AA_YMD"]), default=None)


class NeisNextSchooldaySensor(NeisSchoolEntity, SensorEntity):
    """Date of the next schoolday."""

    _attr_translation_key = "next_schoolday"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_next_schoolday"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.upcoming_schedule.complete

    @property
    def native_value(self) -> date | None:
        return next_schoolday(
            self.coordinator.data.local_date,
            self.coordinator.data.upcoming_schedule,
            self.coordinator.grade,
            SCHEDULE_LOOKAHEAD_DAYS,
        )


class NeisTimetableSensor(NeisSchoolEntity, SensorEntity):
    """Today or tomorrow timetable."""

    _unrecorded_attributes = frozenset({"lessons", "timetable_text", "timetable_tts"})

    def __init__(self, coordinator: NeisSchoolCoordinator, day_offset: int) -> None:
        super().__init__(coordinator)
        self._day_offset = day_offset
        day_key = "today" if day_offset == 0 else "tomorrow"
        self._attr_translation_key = f"timetable_{day_key}"
        self._attr_unique_id = f"{coordinator.school_code}_timetable_{day_key}"

    @property
    def available(self) -> bool:
        response = self.coordinator.data.timetables.get(self._target_date)
        if response is None or not response.complete:
            return False
        if response.rows:
            return super().available
        result = self._schoolday
        return super().available and result.available and result.is_schoolday is False

    @property
    def native_value(self) -> int:
        response = self.coordinator.data.timetables[self._target_date]
        return len(response.rows)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        response = self.coordinator.data.timetables[self._target_date]
        lessons, text, timetable_tts = format_timetable(
            self._target_date, response.rows
        )
        status = "available" if lessons else self._schoolday.reason
        return {
            "date": self._target_date.isoformat(),
            "status": status,
            "period_count": len(lessons),
            "lessons": lessons,
            "timetable_text": text,
            "timetable_tts": timetable_tts,
            "loaded_at": response.rows[0].get("LOAD_DTM") if response.rows else None,
            "data_complete": response.complete,
        }

    @property
    def _target_date(self) -> date:
        return self.coordinator.data.local_date + timedelta(days=self._day_offset)

    @property
    def _schoolday(self):
        return evaluate_schoolday(
            self._target_date,
            self.coordinator.data.schedules[self._target_date],
            self.coordinator.grade,
        )


class NeisApiModeSensor(NeisSchoolEntity, SensorEntity):
    """Diagnostic sensor for full or limited API mode."""

    _attr_translation_key = "api_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["full", "limited"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_api_mode"

    @property
    def native_value(self) -> str:
        return "full" if self.coordinator.api.has_api_key else "limited"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"incomplete_sources": sorted(self.coordinator.data.incomplete_sources)}


class NeisLastUpdateSensor(NeisSchoolEntity, SensorEntity):
    """Diagnostic timestamp for the last successful update."""

    _attr_translation_key = "last_successful_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NeisSchoolCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.school_code}_last_successful_update"

    @property
    def native_value(self):
        return self.coordinator.data.last_success
