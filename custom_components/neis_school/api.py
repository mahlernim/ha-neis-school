"""Async client for the NEIS education information Open API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import PAGE_SIZE, REQUEST_TIMEOUT_SECONDS, SCHOOL_KIND_ENDPOINTS
from .models import NeisResponse

BASE_URL = "https://open.neis.go.kr/hub"


class NeisError(Exception):
    """Base NEIS exception."""


class NeisConnectionError(NeisError):
    """Raised when NEIS cannot be reached."""


class NeisApiError(NeisError):
    """Raised when NEIS returns an API error."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize a sanitized API error."""
        super().__init__(f"NEIS API error {code}: {message}")
        self.code = code


class NeisAPI:
    """Access NEIS public school data without exposing credentials."""

    def __init__(self, session: ClientSession, api_key: str | None = None) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key.strip() if api_key else None

    @property
    def has_api_key(self) -> bool:
        """Return whether complete-data mode is configured."""
        return bool(self._api_key)

    async def _request(
        self,
        endpoint: str,
        params: Mapping[str, str | int],
        *,
        paginate: bool = True,
    ) -> NeisResponse:
        """Request and normalize an endpoint response."""
        base_params: dict[str, str | int] = {"Type": "json", **params}
        if self._api_key:
            base_params["KEY"] = self._api_key

        if not self._api_key or not paginate:
            return await self._request_page(endpoint, base_params)

        page = 1
        rows: list[dict[str, Any]] = []
        total_count = 0
        result_code = "INFO-000"
        while True:
            page_params = {
                **base_params,
                "pIndex": page,
                "pSize": PAGE_SIZE,
            }
            response = await self._request_page(endpoint, page_params)
            total_count = response.total_count
            result_code = response.result_code
            rows.extend(response.rows)
            if not response.rows or len(rows) >= total_count:
                break
            page += 1

        return NeisResponse(
            tuple(rows),
            total_count,
            len(rows) >= total_count,
            result_code,
        )

    async def _request_page(
        self, endpoint: str, params: Mapping[str, str | int]
    ) -> NeisResponse:
        """Request one NEIS response page."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                async with self._session.get(
                    f"{BASE_URL}/{endpoint}", params=params
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
        except (TimeoutError, ClientError, json.JSONDecodeError, ValueError) as err:
            raise NeisConnectionError("Unable to communicate with NEIS") from err

        direct_result = payload.get("RESULT")
        if direct_result:
            code = str(direct_result.get("CODE", "ERROR"))
            if code == "INFO-200":
                return NeisResponse.empty(code)
            raise NeisApiError(code, str(direct_result.get("MESSAGE", "Unknown error")))

        container = payload.get(endpoint)
        if not isinstance(container, list) or len(container) < 2:
            raise NeisApiError("INVALID_RESPONSE", "Unexpected response structure")

        head = container[0].get("head", [])
        total_count = 0
        result_code = "INFO-000"
        for item in head:
            if "list_total_count" in item:
                total_count = int(item["list_total_count"])
            if "RESULT" in item:
                result = item["RESULT"]
                result_code = str(result.get("CODE", "ERROR"))
                if result_code not in ("INFO-000", "INFO-200"):
                    raise NeisApiError(
                        result_code, str(result.get("MESSAGE", "Unknown error"))
                    )

        rows = tuple(container[1].get("row", []))
        return NeisResponse(
            rows,
            total_count,
            len(rows) >= total_count,
            result_code,
        )

    async def search_schools(self, office_code: str, school_name: str) -> NeisResponse:
        """Search schools by office and name."""
        return await self._request(
            "schoolInfo",
            {"ATPT_OFCDC_SC_CODE": office_code, "SCHUL_NM": school_name},
        )

    async def get_classes(
        self,
        office_code: str,
        school_code: str,
        academic_year: int,
        grade: int,
        class_name: str | None = None,
    ) -> NeisResponse:
        """Return classes for a school and grade."""
        params: dict[str, str | int] = {
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
            "AY": academic_year,
            "GRADE": grade,
        }
        if class_name:
            params["CLASS_NM"] = class_name
        return await self._request("classInfo", params)

    async def get_meals(
        self, office_code: str, school_code: str, meal_date: date
    ) -> NeisResponse:
        """Return all meals for one date."""
        return await self._request(
            "mealServiceDietInfo",
            {
                "ATPT_OFCDC_SC_CODE": office_code,
                "SD_SCHUL_CODE": school_code,
                "MLSV_YMD": meal_date.strftime("%Y%m%d"),
            },
        )

    async def get_schedule(
        self,
        office_code: str,
        school_code: str,
        start_date: date,
        end_date: date,
    ) -> NeisResponse:
        """Return school schedule rows in an inclusive date range."""
        params: dict[str, str | int] = {
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
        }
        if start_date == end_date:
            params["AA_YMD"] = start_date.strftime("%Y%m%d")
        else:
            params["AA_FROM_YMD"] = start_date.strftime("%Y%m%d")
            params["AA_TO_YMD"] = end_date.strftime("%Y%m%d")
        return await self._request("SchoolSchedule", params)

    async def get_timetable(
        self,
        office_code: str,
        school_code: str,
        school_kind: str,
        timetable_date: date,
        grade: int,
        class_name: str,
    ) -> NeisResponse:
        """Return a class timetable for one date."""
        endpoint = SCHOOL_KIND_ENDPOINTS.get(school_kind)
        if endpoint is None:
            raise NeisApiError("UNSUPPORTED_SCHOOL", school_kind)
        return await self._request(
            endpoint,
            {
                "ATPT_OFCDC_SC_CODE": office_code,
                "SD_SCHUL_CODE": school_code,
                "ALL_TI_YMD": timetable_date.strftime("%Y%m%d"),
                "GRADE": grade,
                "CLASS_NM": class_name,
            },
        )
