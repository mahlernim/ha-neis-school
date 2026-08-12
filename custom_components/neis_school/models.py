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

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "rows": list(self.rows),
            "total_count": self.total_count,
            "complete": self.complete,
            "result_code": self.result_code,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> NeisResponse:
        """Restore a normalized response from storage."""
        rows = value.get("rows", [])
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Invalid cached NEIS rows")
        return cls(
            tuple(rows),
            int(value["total_count"]),
            bool(value["complete"]),
            str(value["result_code"]),
        )


@dataclass(slots=True)
class NeisCoordinatorData:
    """Data shared by NEIS School entities."""

    local_date: date
    meals: dict[date, NeisResponse]
    schedules: dict[date, NeisResponse]
    timetables: dict[date, NeisResponse]
    upcoming_schedule: NeisResponse
    last_success: datetime
    last_attempt: datetime
    incomplete_sources: set[str] = field(default_factory=set)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot."""

        def encode(values: dict[date, NeisResponse]) -> dict[str, dict[str, Any]]:
            return {
                key.isoformat(): response.as_dict() for key, response in values.items()
            }

        return {
            "local_date": self.local_date.isoformat(),
            "meals": encode(self.meals),
            "schedules": encode(self.schedules),
            "timetables": encode(self.timetables),
            "upcoming_schedule": self.upcoming_schedule.as_dict(),
            "last_success": self.last_success.isoformat(),
            "last_attempt": self.last_attempt.isoformat(),
            "incomplete_sources": sorted(self.incomplete_sources),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> NeisCoordinatorData:
        """Restore a coordinator snapshot from storage."""

        def decode(values: dict[str, Any]) -> dict[date, NeisResponse]:
            return {
                date.fromisoformat(key): NeisResponse.from_dict(response)
                for key, response in values.items()
            }

        return cls(
            local_date=date.fromisoformat(value["local_date"]),
            meals=decode(value["meals"]),
            schedules=decode(value["schedules"]),
            timetables=decode(value["timetables"]),
            upcoming_schedule=NeisResponse.from_dict(value["upcoming_schedule"]),
            last_success=datetime.fromisoformat(value["last_success"]),
            last_attempt=datetime.fromisoformat(value["last_attempt"]),
            incomplete_sources=set(value.get("incomplete_sources", [])),
        )


@dataclass(slots=True, frozen=True)
class SchooldayResult:
    """A schoolday evaluation result."""

    available: bool
    is_schoolday: bool | None
    reason: str
    events: tuple[str, ...]
