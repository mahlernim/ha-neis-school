"""Tests for parsing and schoolday decisions."""

from datetime import date

from custom_components.neis_school.helpers import (
    clean_menu,
    evaluate_schoolday,
    next_schoolday,
    parse_allergens,
    parse_calories,
    parse_label_values,
)
from custom_components.neis_school.models import NeisResponse


def response(*rows, complete=True) -> NeisResponse:
    return NeisResponse(tuple(rows), len(rows), complete, "INFO-000")


def test_weekend_is_not_schoolday() -> None:
    result = evaluate_schoolday(date(2026, 8, 8), response(), 6)
    assert result.available
    assert result.is_schoolday is False
    assert result.reason == "weekend"


def test_vacation_is_not_schoolday() -> None:
    result = evaluate_schoolday(
        date(2026, 8, 5),
        response(
            {
                "EVENT_NM": "여름방학",
                "SIX_GRADE_EVENT_YN": "Y",
                "SBTR_DD_SC_NM": "휴업일",
            }
        ),
        6,
    )
    assert result.is_schoolday is False
    assert result.reason == "여름방학"


def test_other_grade_event_is_ignored() -> None:
    result = evaluate_schoolday(
        date(2026, 8, 5),
        response(
            {
                "EVENT_NM": "5학년 재량휴업일",
                "SIX_GRADE_EVENT_YN": "N",
                "SBTR_DD_SC_NM": "휴업일",
            }
        ),
        6,
    )
    assert result.is_schoolday is True


def test_incomplete_schedule_is_unavailable() -> None:
    result = evaluate_schoolday(
        date(2026, 8, 5), response({"EVENT_NM": "sample"}, complete=False), 6
    )
    assert result.available is False
    assert result.is_schoolday is None


def test_next_schoolday_skips_vacation_and_weekend() -> None:
    schedule = response(
        {
            "AA_YMD": "20260807",
            "EVENT_NM": "여름방학",
            "SIX_GRADE_EVENT_YN": "Y",
            "SBTR_DD_SC_NM": "휴업일",
        }
    )
    assert next_schoolday(date(2026, 8, 6), schedule, 6, 7) == date(2026, 8, 10)


def test_meal_parsers() -> None:
    raw = "귀리밥 <br/>육개장 (2.5.6.9.16.18)<br/>♥한라봉"
    assert clean_menu(raw) == "귀리밥 , 육개장 , 한라봉"
    assert parse_allergens(raw) == [2, 5, 6, 9, 16, 18]
    assert parse_calories("676.2 Kcal") == 676.2
    assert parse_label_values("탄수화물(g) : 73.8<br/>단백질(g) : 20.7") == {
        "탄수화물(g)": "73.8",
        "단백질(g)": "20.7",
    }
