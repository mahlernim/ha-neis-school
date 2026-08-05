"""Tests for schedule sensor presentation contracts."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.neis_school.calendar import NeisSchoolCalendar
from custom_components.neis_school.const import (
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
)
from custom_components.neis_school.models import NeisResponse
from custom_components.neis_school.sensor import (
    NeisScheduleTodaySensor,
    NeisTimetableSensor,
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


async def test_calendar_reuses_an_identical_range_request() -> None:
    api = SimpleNamespace(
        has_api_key=True,
        get_schedule=AsyncMock(return_value=NeisResponse.empty()),
    )
    coordinator = SimpleNamespace(
        api=api,
        office_code="C10",
        school_code="7201202",
        grade=6,
        data=SimpleNamespace(
            local_date=date(2026, 8, 5),
            upcoming_schedule=NeisResponse.empty(),
        ),
        entry=SimpleNamespace(data={CONF_SCHOOL_NAME: "테스트학교"}),
    )
    calendar = object.__new__(NeisSchoolCalendar)
    calendar.coordinator = coordinator
    calendar._range_cache = {}
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)

    assert await calendar.async_get_events(None, start, end) == []
    assert await calendar.async_get_events(None, start, end) == []
    assert api.get_schedule.await_count == 1


def test_empty_complete_timetable_remains_available() -> None:
    target_date = date(2026, 8, 5)
    empty = NeisResponse.empty()
    coordinator = SimpleNamespace(
        last_update_success=True,
        data=SimpleNamespace(
            local_date=target_date,
            timetables={target_date: empty},
            schedules={target_date: empty},
        ),
        grade=6,
        class_name="2",
        school_code="7201202",
        entry=SimpleNamespace(
            entry_id="entry-id",
            title="테스트학교 6학년 2반",
            data={
                CONF_SCHOOL_NAME: "테스트학교",
                CONF_SCHOOL_KIND: "초등학교",
                CONF_SCHOOL_HOMEPAGE: None,
            },
        ),
    )
    sensor = NeisTimetableSensor(coordinator, 0)

    assert sensor.available
    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["status"] == "no_timetable"
