"""Every API route requires a signed-in user, except an explicit public allowlist.

Adding a route without `require_roles(...)` / `get_current_principal` fails this test
(Level 3 exit gate: "roles enforced on every API").
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi.routing import APIRoute

from planner.core.security import get_current_principal
from planner.main import app

PUBLIC = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/auth/invites/{token}/accept"),
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("GET", "/metrics"),
    ("GET", "/"),
}


def _routes(routes: list[Any]) -> Iterator[APIRoute]:
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):  # FastAPI >= 0.140 nests included routers
            yield from _routes(r.original_router.routes)


def _calls(dependant: Any) -> Iterator[Any]:
    for d in dependant.dependencies:
        yield d.call
        yield from _calls(d)


def test_every_route__requires_auth_unless_public() -> None:
    open_routes = sorted(
        (method, r.path)
        for r in _routes(app.routes)
        for method in r.methods
        if get_current_principal not in set(_calls(r.dependant))
        and (method, r.path) not in PUBLIC
    )
    assert not open_routes, f"routes without an auth dependency: {open_routes}"
