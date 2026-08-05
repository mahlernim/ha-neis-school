"""Credential-safe live smoke test for public NEIS data."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
import types
from datetime import date, timedelta
from pathlib import Path

import aiohttp

if importlib.util.find_spec("homeassistant") is None:
    root = types.ModuleType("custom_components")
    root.__path__ = [str(Path(__file__).parents[1] / "custom_components")]
    sys.modules["custom_components"] = root
    package = types.ModuleType("custom_components.neis_school")
    package.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "neis_school")
    ]
    sys.modules["custom_components.neis_school"] = package

NeisAPI = importlib.import_module("custom_components.neis_school.api").NeisAPI


def _load_key() -> str:
    value = os.getenv("NEIS_API_KEY", "").strip()
    if value:
        return value
    env_file = Path(__file__).resolve().parents[1] / "env.txt"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("NEIS_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("NEIS_API_KEY is not configured")


def _required_env(name: str) -> str:
    """Load a required smoke-test target without hardcoding a classroom."""
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is not configured")
    return value


async def main() -> None:
    """Verify completeness without printing the key or request URL."""
    key = _load_key()
    office_code = _required_env("NEIS_OFFICE_CODE")
    school_code = _required_env("NEIS_SCHOOL_CODE")
    school_kind = _required_env("NEIS_SCHOOL_KIND")
    grade = int(_required_env("NEIS_GRADE"))
    class_name = _required_env("NEIS_CLASS_NAME")
    test_date = date.fromisoformat(_required_env("NEIS_TEST_DATE"))
    academic_year = test_date.year if test_date.month >= 3 else test_date.year - 1
    schedule_start = test_date.replace(day=1)
    next_month = (schedule_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    schedule_end = next_month - timedelta(days=1)
    async with aiohttp.ClientSession() as session:
        full = NeisAPI(session, key)
        limited = NeisAPI(session)
        full_classes = await full.get_classes(
            office_code, school_code, academic_year, grade
        )
        limited_classes = await limited.get_classes(
            office_code, school_code, academic_year, grade
        )
        full_timetable = await full.get_timetable(
            office_code,
            school_code,
            school_kind,
            test_date,
            grade,
            class_name,
        )
        limited_timetable = await limited.get_timetable(
            office_code,
            school_code,
            school_kind,
            test_date,
            grade,
            class_name,
        )
        full_schedule = await full.get_schedule(
            office_code, school_code, schedule_start, schedule_end
        )
        limited_schedule = await limited.get_schedule(
            office_code, school_code, schedule_start, schedule_end
        )
    print(
        "classes",
        f"limited={len(limited_classes.rows)}/{limited_classes.total_count}",
        f"full={len(full_classes.rows)}/{full_classes.total_count}",
    )
    print(
        "timetable",
        f"limited={len(limited_timetable.rows)}/{limited_timetable.total_count}",
        f"full={len(full_timetable.rows)}/{full_timetable.total_count}",
    )
    print(
        "schedule",
        f"limited={len(limited_schedule.rows)}/{limited_schedule.total_count}",
        f"full={len(full_schedule.rows)}/{full_schedule.total_count}",
    )
    if not all(
        (full_classes.complete, full_timetable.complete, full_schedule.complete)
    ):
        raise SystemExit("Authenticated NEIS data is incomplete")


if __name__ == "__main__":
    asyncio.run(main())
