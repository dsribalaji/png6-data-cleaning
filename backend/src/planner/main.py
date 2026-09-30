"""FastAPI application factory (Backend.md).

Base path ``/api/v1``, OpenAPI at ``/api/docs``, health at ``/api/v1/health/live``
and ``/api/v1/health/ready``. Errors are ``application/problem+json``
(RFC 9457) via the handlers in ``planner.core.errors``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import SessionLocal as AsyncSessionLocal
from planner.core.db import engine, uuid7
from planner.core.errors import (
    AppError,
    app_error_handler,
    problem_response,
    request_validation_handler,
    unhandled_handler,
)
from planner.modules.datasets.public import routers as datasets_routers
from planner.modules.users.public import routers as users_routers

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger(__name__)

API_V1_PREFIX = "/api/v1"

# Sibling modules owned by the other slices; imported when their public surface exists.
OPTIONAL_MODULES: tuple[str, ...] = (
    "profiling",
    "planning",
    "execution",
    "validation",
    "model_config",
    "audit",
    "evaluation",
)


def _cors_origins() -> list[str]:
    """Normalise CORS origins from settings (list or comma-separated string)."""
    origins = settings.cors_origins
    if isinstance(origins, str):
        return [o.strip() for o in origins.split(",") if o.strip()]
    return list(origins)


def _local_storage_file(key: str) -> Path | None:
    """Resolve a storage key under the local root, or None when out of bounds.

    Guards against path traversal: the resolved path must stay under the root.
    """
    if settings.storage_backend != "local":
        return None

    root = Path(settings.storage_local_root).resolve()
    candidate = (root / key.lstrip("/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Mounts every module's feature routers (each already carries its full
    ``/api/v1`` prefix), the local file server used by local demo mode, the
    health probes, and the Prometheus scrape endpoint.
    """
    app = FastAPI(
        title="Agentic Data Cleaning Planner",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/docs/openapi.json",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Attach X-Request-ID to every response and log the request outcome."""
        request_id = uuid7().hex
        request.state.request_id = request_id
        started = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.2f ms) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_handler)

    for router in users_routers:
        app.include_router(router)
    for router in datasets_routers:
        app.include_router(router)

    for module_name in OPTIONAL_MODULES:
        try:
            module = __import__(
                f"planner.modules.{module_name}.public", fromlist=["routers"]
            )
        except ImportError:
            logger.warning("module %s routers not available yet", module_name)
            continue
        for router in getattr(module, "routers", []):
            app.include_router(router)

    @app.get(f"{API_V1_PREFIX}/files/{{key:path}}", tags=["files"], response_model=None)
    async def serve_file(key: str) -> Response:
        """Serve a stored object by key in local demo mode (S3/MinIO uses presigned URLs)."""
        if settings.storage_backend != "local":
            return problem_response(
                status=404,
                title="NOT_FOUND",
                detail="Local file serving is disabled for the configured storage backend.",
                code="NOT_FOUND",
            )

        path = _local_storage_file(key)
        if path is None or not path.is_file():
            return problem_response(
                status=404,
                title="NOT_FOUND",
                detail="The requested resource was not found.",
                code="NOT_FOUND",
            )
        return FileResponse(path)

    @app.get(f"{API_V1_PREFIX}/health/live", tags=["health"])
    async def health_live() -> dict[str, str]:
        """Liveness probe (public)."""
        return {"status": "ok"}

    @app.get(f"{API_V1_PREFIX}/health/ready", tags=["health"], response_model=None)
    async def health_ready() -> Response:
        """Readiness probe: the database answers a trivial query."""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            logger.warning("readiness check failed: %s", exc)
            return problem_response(
                status=503,
                title="NOT_READY",
                detail="The database is not reachable.",
                code="NOT_READY",
            )
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/metrics", tags=["health"], response_model=None)
    async def metrics() -> Response:
        """Prometheus scrape endpoint; 404 when prometheus_client is unavailable."""
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        except ImportError:
            return problem_response(
                status=404,
                title="NOT_FOUND",
                detail="The requested resource was not found.",
                code="NOT_FOUND",
            )
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", tags=["service"], response_model=None)
    async def root() -> dict[str, str]:
        """Service banner pointing at the OpenAPI docs."""
        return {"service": "planner", "version": "0.1.0", "docs": "/api/docs"}

    @app.on_event("startup")
    async def register_shared_tasks() -> None:
        """Import the shared-task modules so their Celery tasks are registered (local demo)."""
        if not settings.celery_task_always_eager:
            return
        for module_name in (
            "planner.modules.datasets.tasks",
            "planner.core.outbox",
        ):
            try:
                __import__(module_name)
            except ImportError as exc:
                logger.warning("could not import %s at startup: %s", module_name, exc)

    return app


app = create_app()