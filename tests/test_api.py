"""Tests for the NEIS API client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aiohttp import web

from custom_components.neis_school import api as api_module
from custom_components.neis_school.api import NeisAPI


@pytest.fixture(autouse=True)
def allow_local_test_server(enable_socket) -> None:
    """Allow aiohttp to bind the loopback test server."""

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_limited_response_is_detected(aiohttp_client, monkeypatch) -> None:
    """An anonymous first-five sample must be marked incomplete."""
    app = web.Application()

    async def handler(_request):
        return web.json_response(load_fixture("class_limited.json"))

    app.router.add_get("/classInfo", handler)
    client = await aiohttp_client(app)
    monkeypatch.setattr(api_module, "BASE_URL", str(client.make_url("/")).rstrip("/"))

    response = await NeisAPI(client.session).get_classes("C10", "7201202", 2026, 6)
    assert len(response.rows) == 5
    assert response.total_count == 6
    assert response.complete is False


@pytest.mark.asyncio
async def test_authenticated_response_paginates(aiohttp_client, monkeypatch) -> None:
    """Authenticated mode must collect every page."""
    app = web.Application()

    async def handler(request):
        assert request.query["KEY"] == "test-key"
        fixture = (
            "class_limited.json"
            if request.query["pIndex"] == "1"
            else "class_last_page.json"
        )
        return web.json_response(load_fixture(fixture))

    app.router.add_get("/classInfo", handler)
    client = await aiohttp_client(app)
    monkeypatch.setattr(api_module, "BASE_URL", str(client.make_url("/")).rstrip("/"))

    response = await NeisAPI(client.session, "test-key").get_classes(
        "C10", "7201202", 2026, 6
    )
    assert [row["CLASS_NM"] for row in response.rows] == ["1", "2", "3", "4", "5", "6"]
    assert response.complete is True


@pytest.mark.asyncio
async def test_info_200_is_complete_empty(aiohttp_client, monkeypatch) -> None:
    """No matching data is not a transport failure."""
    app = web.Application()

    async def handler(_request):
        return web.json_response(
            {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
        )

    app.router.add_get("/mealServiceDietInfo", handler)
    client = await aiohttp_client(app)
    monkeypatch.setattr(api_module, "BASE_URL", str(client.make_url("/")).rstrip("/"))

    response = await NeisAPI(client.session).get_meals(
        "C10", "7201202", api_module.date(2026, 8, 5)
    )
    assert response.rows == ()
    assert response.complete is True
    assert response.result_code == "INFO-200"


@pytest.mark.parametrize(
    ("kind", "endpoint"),
    [
        ("초등학교", "elsTimetable"),
        ("중학교", "misTimetable"),
        ("고등학교", "hisTimetable"),
        ("특수학교", "spsTimetable"),
    ],
)
@pytest.mark.asyncio
async def test_timetable_endpoint_mapping(
    aiohttp_client, monkeypatch, kind, endpoint
) -> None:
    """Every supported school kind must use its own endpoint."""
    app = web.Application()

    async def handler(_request):
        return web.json_response({"RESULT": {"CODE": "INFO-200", "MESSAGE": "none"}})

    app.router.add_get(f"/{endpoint}", handler)
    client = await aiohttp_client(app)
    monkeypatch.setattr(api_module, "BASE_URL", str(client.make_url("/")).rstrip("/"))
    response = await NeisAPI(client.session).get_timetable(
        "C10", "7201202", kind, api_module.date(2026, 3, 5), 6, "2"
    )
    assert response.complete
