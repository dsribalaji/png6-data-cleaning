"""API health checks (foundation, Backend.md test naming)."""

from fastapi.testclient import TestClient

from planner.main import app

client = TestClient(app)


def test_health_live__no_db__returns_200() -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi__served_at_api_docs__returns_200() -> None:
    r = client.get("/api/docs/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Agentic Data Cleaning Planner"
