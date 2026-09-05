"""Tests for schedule sensor presentation contracts."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.neis_school.calendar import NeisSchoolCalendar
from custom_components.neis_school.const import (
    CONF_SCHOOL_HOMEPAGE,
    CONF_SCHOOL_KIND,
    CONF_SCHOOL_NAME,
    SCHEDULE_LOOKAHEAD_DAYS,
)
from custom_components.neis_school.entity import _normalize_configuration_url
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


def test_configuration_url_adds_a_missing_scheme() -> None:
    assert (
        _normalize_configuration_url("school.example.kr/home")
        == "https://school.example.kr/home"
    )


def test_configuration_url_preserves_a_valid_scheme() -> None:
    assert (
        _normalize_configuration_url("http://school.example.kr")
        == "http://school.example.kr"
    )


def test_configuration_url_omits_invalid_values() -> None:
    assert _normalize_configuration_url(None) is None
    assert _normalize_configuration_url("ftp://school.example.kr") is None


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
            schedules={},
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


async def test_calendar_fetches_beyond_actual_cached_dates_after_midnight() -> None:
    """Moving the display date must not invent coverage for unfetched days."""
    fetched_date = date(2026, 8, 5)
    cached_end = fetched_date + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS)
    requested_date = cached_end + timedelta(days=1)
    event = {
        "AA_YMD": requested_date.strftime("%Y%m%d"),
        "EVENT_NM": "학부모 상담",
    }
    api = SimpleNamespace(
        has_api_key=True,
        get_schedule=AsyncMock(
            return_value=NeisResponse((event,), 1, True, "INFO-000")
        ),
    )
    coordinator = SimpleNamespace(
        api=api,
        office_code="C10",
        school_code="7201202",
        grade=6,
        data=SimpleNamespace(
            local_date=fetched_date + timedelta(days=1),
            upcoming_schedule=NeisResponse.empty(),
            schedules={
                fetched_date + timedelta(days=offset): NeisResponse.empty()
                for offset in range(SCHEDULE_LOOKAHEAD_DAYS + 1)
            },
        ),
        entry=SimpleNamespace(data={CONF_SCHOOL_NAME: "테스트학교"}),
    )
    calendar = object.__new__(NeisSchoolCalendar)
    calendar.coordinator = coordinator
    calendar._range_cache = {}
    start = datetime.combine(requested_date, datetime.min.time(), tzinfo=UTC)

    events = await calendar.async_get_events(None, start, start + timedelta(days=1))

    api.get_schedule.assert_awaited_once_with(
        "C10", "7201202", requested_date, requested_date
    )
    assert len(events) == 1
    assert events[0].summary == "학부모 상담"
    assert calendar._coordinator_response(cached_end, cached_end) is not None


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


def test_timetable_state_counts_only_valid_lessons() -> None:
    target_date = date(2026, 8, 5)
    raw_rows = tuple(
        {"PERIO": str(period), "ITRT_CNTNT": None} for period in range(1, 9)
    )
    response = NeisResponse(raw_rows, len(raw_rows), True, "INFO-000")
    coordinator = SimpleNamespace(
        last_update_success=True,
        data=SimpleNamespace(
            local_date=target_date,
            timetables={target_date: response},
            schedules={target_date: NeisResponse.empty()},
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

    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["period_count"] == 0
    assert sensor.extra_state_attributes["timetable_tts"] == ""
