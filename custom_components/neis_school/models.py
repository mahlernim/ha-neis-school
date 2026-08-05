"""Data models for the NEIS School integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class NeisResponse:
    """A normalized NEIS Open API response."""

    rows: tuple[dict[str, Any], ...]
    total_count: int
    complete: bool
    result_code: str

    @classmethod
    def empty(cls, result_code: str = "INFO-200") -> NeisResponse:
        """Return a complete empty response."""
        return cls((), 0, True, result_code)

    @classmethod
    def limited(cls) -> NeisResponse:
        """Return a deliberately unavailable limited-mode response."""
        return cls((), 0, False, "LIMITED_MODE")


@dataclass(slots=True)
class NeisCoordinatorData:
    """Data shared by NEIS School entities."""

    local_date: date
    meals: dict[date, NeisResponse]
    schedules: dict[date, NeisResponse]
    timetables: dict[date, NeisResponse]
    upcoming_schedule: NeisResponse
    last_success: datetime
    incomplete_sources: set[str] = field(default_factory=set)


@dataclass(slots=True, frozen=True)
class SchooldayResult:
    """A schoolday evaluation result."""

    available: bool
    is_schoolday: bool | None
    reason: str
    events: tuple[str, ...]
