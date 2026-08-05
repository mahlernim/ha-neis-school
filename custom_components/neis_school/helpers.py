"""Shared parsing and schoolday helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from .const import GRADE_EVENT_FIELDS
from .models import NeisResponse, SchooldayResult

_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_PAREN_RE = re.compile(r"\(([^)]*)\)")
_ALLERGEN_RE = re.compile(r"(?<!\d)(?:\d{1,2})(?!\d)")
_SPECIAL_RE = re.compile(r"[*★♥♡●■□▲▼◆◇]")
_NON_SCHOOL_KEYWORDS = (
    "방학",
    "공휴일",
    "휴업",
    "재량휴업",
    "대체공휴일",
)


def parse_neis_date(value: str) -> date:
    """Parse YYYYMMDD into a date."""
    return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))


def row_applies_to_grade(row: dict[str, Any], grade: int) -> bool:
    """Return whether a schedule row applies to a grade."""
    field = GRADE_EVENT_FIELDS.get(grade)
    if field is None or field not in row:
        return True
    return str(row.get(field, "Y")).upper() != "N"


def applicable_schedule_rows(
    response: NeisResponse, grade: int
) -> tuple[dict[str, Any], ...]:
    """Filter schedule rows for a selected grade."""
    return tuple(row for row in response.rows if row_applies_to_grade(row, grade))


def evaluate_schoolday(
    target_date: date, response: NeisResponse, grade: int
) -> SchooldayResult:
    """Evaluate whether a student should attend school."""
    if target_date.weekday() >= 5:
        return SchooldayResult(True, False, "weekend", ())
    if not response.complete:
        return SchooldayResult(False, None, "incomplete_data", ())

    rows = applicable_schedule_rows(response, grade)
    events = tuple(str(row.get("EVENT_NM", "")).strip() for row in rows)
    events = tuple(event for event in events if event)
    for row in rows:
        event_name = str(row.get("EVENT_NM", ""))
        deduction = str(row.get("SBTR_DD_SC_NM", ""))
        if deduction == "휴업일" or any(
            keyword in event_name for keyword in _NON_SCHOOL_KEYWORDS
        ):
            return SchooldayResult(
                True,
                False,
                event_name or deduction or "no_school",
                events,
            )
    return SchooldayResult(True, True, "regular_schoolday", events)


def clean_menu(raw_menu: str | None) -> str:
    """Clean a menu for display and TTS."""
    if not raw_menu:
        return ""
    cleaned = _PAREN_RE.sub("", raw_menu)
    cleaned = re.sub(r"\d+/\d+", "", cleaned)
    cleaned = _BREAK_RE.sub(", ", cleaned).replace("/", ", ")
    cleaned = _SPECIAL_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    return cleaned.strip(", ")


def format_meal_tts(
    target_date: date, school_name: str, meal_name: str, menu: str
) -> str:
    """Return a natural Korean meal announcement, including no-meal days."""
    prefix = f"{target_date.month}월 {target_date.day}일 {school_name}"
    if not menu:
        return f"{prefix}에는 {meal_name}이 없습니다."
    return f"{prefix} {meal_name} 메뉴는 {menu}입니다."


def format_timetable(
    target_date: date, rows: tuple[dict[str, Any], ...]
) -> tuple[list[dict[str, Any]], str, str]:
    """Return normalized timetable data and text without null placeholders."""
    lessons: list[dict[str, Any]] = []
    for row in rows:
        try:
            period = int(row.get("PERIO") or 0)
        except (TypeError, ValueError):
            continue
        subject = str(row.get("ITRT_CNTNT") or "").strip()
        if period < 1 or not subject:
            continue
        lessons.append({"period": period, "subject": subject})

    lessons.sort(key=lambda lesson: lesson["period"])
    text = ", ".join(
        f"{lesson['period']}교시 {lesson['subject']}" for lesson in lessons
    )
    tts = (
        f"{target_date.month}월 {target_date.day}일 시간표는 {text}입니다."
        if text
        else ""
    )
    return lessons, text, tts


def parse_allergens(raw_menu: str | None) -> list[int]:
    """Extract NEIS allergen numbers from parenthesized menu annotations."""
    if not raw_menu:
        return []
    values: set[int] = set()
    for annotation in _PAREN_RE.findall(raw_menu):
        for value in _ALLERGEN_RE.findall(annotation):
            number = int(value)
            if 1 <= number <= 19:
                values.add(number)
    return sorted(values)


def parse_label_values(raw: str | None) -> dict[str, str]:
    """Parse NEIS line-separated label and value fields."""
    if not raw:
        return {}
    parsed: dict[str, str] = {}
    for line in _BREAK_RE.split(raw):
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        value = value.strip()
        if label and value:
            parsed[label] = value
    return parsed


def parse_origin_lines(raw: str | None) -> list[str]:
    """Return non-empty origin information lines."""
    if not raw:
        return []
    return [line.strip() for line in _BREAK_RE.split(raw) if line.strip()]


def parse_calories(raw: str | None) -> float | None:
    """Extract a numeric calorie value."""
    if not raw:
        return None
    match = re.search(r"\d+(?:\.\d+)?", raw)
    return float(match.group()) if match else None


def rows_by_date(rows: tuple[dict[str, Any], ...]) -> dict[date, list[dict[str, Any]]]:
    """Group schedule rows by academic date."""
    grouped: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get("AA_YMD", ""))
        if len(value) == 8:
            grouped[parse_neis_date(value)].append(row)
    return dict(grouped)


def next_schoolday(
    start_date: date,
    schedule: NeisResponse,
    grade: int,
    lookahead_days: int,
) -> date | None:
    """Return the next schoolday after start_date."""
    if not schedule.complete:
        return None
    grouped = rows_by_date(schedule.rows)
    for offset in range(1, lookahead_days + 1):
        candidate = start_date + timedelta(days=offset)
        response = NeisResponse(
            tuple(grouped.get(candidate, [])),
            len(grouped.get(candidate, [])),
            True,
            "INFO-000",
        )
        result = evaluate_schoolday(candidate, response, grade)
        if result.is_schoolday:
            return candidate
    return None
