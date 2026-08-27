import asyncio

import httpx

from fixtrace.api.app import _safe_task_request, app
from fixtrace.core.models import AnalysisRequest


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
    assert response.json()["agent"]["read_only_tools"] is True


def test_missing_analysis_is_404() -> None:
    response = request("/api/analyses/not-found")

    assert response.status_code == 404


def test_homepage_is_served() -> None:
    response = request("/")

    assert response.status_code == 200
    assert "An agent that investigates" in response.text


def test_task_metadata_is_sanitized_before_storage() -> None:
    secret = "synthetic-api-secret-value"
    request_model = AnalysisRequest(
        failure_output=f"password={secret}\nRuntimeError: request failed"
    )

    sanitized = _safe_task_request(request_model)

    assert secret not in sanitized.failure_output
    assert "[REDACTED]" in sanitized.failure_output


def test_analysis_api_returns_agent_state() -> None:
    async def scenario() -> dict:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/analyses",
                json={
                    "failure_output": "GET /health\nHTTP/1.1 503 Service Unavailable",
                    "agent_mode": "auto",
                },
            )
            assert created.status_code == 202
            task_id = created.json()["id"]
            for _ in range(100):
                task = (await client.get(f"/api/analyses/{task_id}")).json()
                if task["status"] not in {"queued", "running"}:
                    return task
                await asyncio.sleep(0.01)
        raise AssertionError("Analysis task did not finish")

    task = asyncio.run(scenario())

    assert task["status"] == "succeeded"
    assert task["report"]["agent"]["status"] == "not_configured"
    assert any(stage["stage"] == "investigate" for stage in task["stages"])
