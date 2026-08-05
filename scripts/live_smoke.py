"""Credential-safe live smoke test for public NEIS data."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
import types
from datetime import date
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


async def main() -> None:
    """Verify completeness without printing the key or request URL."""
    key = _load_key()
    async with aiohttp.ClientSession() as session:
        full = NeisAPI(session, key)
        limited = NeisAPI(session)
        full_classes = await full.get_classes("C10", "7201202", 2026, 6)
        limited_classes = await limited.get_classes("C10", "7201202", 2026, 6)
        full_timetable = await full.get_timetable(
            "C10", "7201202", "초등학교", date(2026, 3, 5), 6, "2"
        )
        limited_timetable = await limited.get_timetable(
            "C10", "7201202", "초등학교", date(2026, 3, 5), 6, "2"
        )
        full_schedule = await full.get_schedule(
            "C10", "7201202", date(2026, 8, 1), date(2026, 8, 31)
        )
        limited_schedule = await limited.get_schedule(
            "C10", "7201202", date(2026, 8, 1), date(2026, 8, 31)
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
