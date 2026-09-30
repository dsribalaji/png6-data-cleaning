"""Health check endpoint test."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    """Verify that GET /health returns 200 OK and status 'ok'."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
