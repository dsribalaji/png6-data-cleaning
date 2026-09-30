"""Every plan/profile/execution/validation endpoint rejects callers without a token."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from planner.main import app

ID = "00000000-0000-0000-0000-000000000000"
PROTECTED = [
    ("GET", f"/api/v1/plans/{ID}"),
    ("POST", f"/api/v1/datasets/{ID}/plans"),
    ("PATCH", f"/api/v1/plans/{ID}/steps/{ID}"),
    ("POST", f"/api/v1/plans/{ID}/approve"),
    ("GET", f"/api/v1/datasets/{ID}/profile"),
    ("GET", f"/api/v1/datasets/{ID}/rules"),
    ("POST", f"/api/v1/plans/{ID}/exports"),
    ("POST", f"/api/v1/plans/{ID}/rollback"),
    ("GET", f"/api/v1/plans/{ID}/versions"),
    ("GET", f"/api/v1/plans/{ID}/validation"),
    ("GET", "/api/v1/files/exports/anything.xlsx"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_endpoint_without_token_is_401(method: str, path: str) -> None:
    r = TestClient(app).request(method, path, json={})
    assert r.status_code == 401, f"{method} {path}: {r.status_code} {r.text}"
