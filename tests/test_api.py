import asyncio

import httpx

from fixtrace.api.app import app


async def _request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def request(path: str) -> httpx.Response:
    return asyncio.run(_request(path))


def test_health_endpoint() -> None:
    response = request("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_analysis_is_404() -> None:
    response = request("/api/analyses/not-found")

    assert response.status_code == 404


def test_homepage_is_served() -> None:
    response = request("/")

    assert response.status_code == 200
    assert "Don’t guess" in response.text
