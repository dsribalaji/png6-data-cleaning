"""D-7: per-client limits on sign-in and upload answer 429 RATE_LIMITED."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from planner.core import ratelimit
from planner.core.config import settings
from planner.core.errors import AppError, app_error_handler
from planner.core.ratelimit import rate_limit


def _app(limit: int) -> TestClient:
    ratelimit._hits.clear()
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)

    @app.post("/x", dependencies=[Depends(rate_limit("t", lambda: limit))])
    def x() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_rate_limit__over_the_limit__429_problem_json() -> None:
    c = _app(3)
    assert [c.post("/x").status_code for _ in range(4)] == [200, 200, 200, 429]
    r = c.post("/x")
    assert r.json()["code"] == "RATE_LIMITED"
    assert r.headers["content-type"].startswith("application/problem+json")


def test_rate_limit__zero__disabled() -> None:
    c = _app(0)
    assert {c.post("/x").status_code for _ in range(50)} == {200}


def test_rate_limit__client_header_only_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _app(1)
    spoof = {"cf-connecting-ip": "1.2.3.4"}
    assert c.post("/x").status_code == 200
    assert c.post("/x", headers=spoof).status_code == 429  # header ignored by default
    monkeypatch.setattr(settings, "rate_limit_client_header", "cf-connecting-ip")
    assert c.post("/x", headers=spoof).status_code == 200  # a different client now


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/datasets"])
def test_login_and_upload__are_rate_limited(path: str) -> None:
    from planner.main import app

    def routes(rs):  # type: ignore[no-untyped-def]
        for r in rs:
            if isinstance(r, APIRoute):
                yield r
            elif hasattr(r, "original_router"):
                yield from routes(r.original_router.routes)

    route = next(r for r in routes(app.routes) if r.path == path and "POST" in r.methods)
    names = {getattr(d.call, "__qualname__", "") for d in route.dependant.dependencies}
    assert any(n.startswith("rate_limit.") for n in names)
