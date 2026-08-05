"""Tests for schedule sensor presentation contracts."""

from datetime import date

from custom_components.neis_school.calendar import NeisSchoolCalendar
from custom_components.neis_school.sensor import (
    NeisScheduleTodaySensor,
    _format_schedule_for_tts,
)


def test_schedule_sensor_has_bounded_enum_state() -> None:
    sensor = object.__new__(NeisScheduleTodaySensor)
    assert sensor.options == ["scheduled", "none"]


def test_schedule_tts_with_multiple_events() -> None:
    text, tts = _format_schedule_for_tts(
        date(2026, 8, 5),
        "테스트학교",
        ["개학식", "학부모 상담"],
    )

    assert text == "개학식, 학부모 상담"
    assert tts == "8월 5일 테스트학교 학사일정은 개학식, 학부모 상담입니다."


def test_schedule_tts_without_events() -> None:
    text, tts = _format_schedule_for_tts(date(2026, 8, 5), "테스트학교", [])

    assert text == ""
    assert tts == "8월 5일 테스트학교에 등록된 학사일정은 없습니다."


def test_calendar_is_disabled_by_default() -> None:
    calendar = object.__new__(NeisSchoolCalendar)
    assert calendar.entity_registry_enabled_default is False
