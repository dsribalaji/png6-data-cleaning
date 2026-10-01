"""Public API and cross-module interfaces for the execution module (Backend.md)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID

import polars as pl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.errors import AppError
from planner.core.ports.adapters.local_storage import (
    LocalStorageAdapter as _CoreLocalStorageAdapter,
)
from planner.core.ports.storage import StoragePort
from planner.modules.execution.errors import ExecutionErrors
from planner.modules.execution.features.create_export.router import (
    router as create_export_router,
)
from planner.modules.execution.features.list_versions.router import (
    router as list_versions_router,
)
from planner.modules.execution.features.rollback_plan.router import (
    router as rollback_plan_router,
)
from planner.modules.execution.models import PipelineVersion

# Mount: for r in routers: app.include_router(r, prefix='/api/v1')
routers = [list_versions_router, rollback_plan_router, create_export_router]


class LocalStorageAdapter(_CoreLocalStorageAdapter):
    """Filesystem-backed StoragePort for local execution.

    Canonical implementation lives in ``planner.core.ports.adapters.local_storage``;
    this subclass keeps the legacy ``put_object``/``get_object``/``list_keys``
    aliases used across the execution tasks, and inherits the app-served
    ``presigned_get_url`` (``/api/v1/files/{key}``) so export downloads work
    from the frontend.
    """

    def __init__(self, root: str | Path = "./storage") -> None:
        super().__init__(root=root)

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Legacy alias for :meth:`put` kept for execution task call sites."""
        await self.put(key, data, content_type)

    async def get_object(self, key: str) -> bytes:
        """Legacy alias for :meth:`get` kept for execution task call sites.

        Translates the core adapter's ``AppError('NOT_FOUND')`` back to
        ``FileNotFoundError`` so existing ``except FileNotFoundError`` handlers
        (e.g. ``read_snapshot_frame``) keep working.
        """
        try:
            return await self.get(key)
        except AppError as exc:
            if exc.code == "NOT_FOUND":
                raise FileNotFoundError(f"Object not found: {key}") from exc
            raise

    async def list_keys(self, prefix: str) -> list[str]:
        """Legacy alias for :meth:`list` kept for execution task call sites."""
        return await self.list(prefix)


def get_storage() -> StoragePort:
    """Storage factory returning the configured StoragePort implementation."""
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "local":
        root = os.getenv("STORAGE_LOCAL_ROOT", "./storage")
        return LocalStorageAdapter(root=root)
    if backend == "s3":
        raise NotImplementedError("S3 adapter not started - W1/datasets owns the MinIO adapter")
    raise ValueError(f"Unknown storage backend: {backend}")


async def get_current_version_no(session: AsyncSession, plan_id: UUID) -> int:
    """Return the current (maximum) executed version number for a plan, or 0 if none."""
    stmt = select(func.max(PipelineVersion.version_no)).where(
        PipelineVersion.plan_id == plan_id
    )
    result = await session.execute(stmt)
    max_no = result.scalar()
    return max_no if max_no is not None else 0


async def read_snapshot_frame(plan_id: UUID, version_no: int) -> pl.DataFrame:
    """Read a snapshot Parquet file as a Polars DataFrame."""
    storage = get_storage()
    key = f"snapshots/{plan_id}/v{version_no}.parquet"
    try:
        data = await storage.get_object(key)
    except FileNotFoundError:
        raise ExecutionErrors.VERSION_NOT_FOUND

    from planner.engine.ingest.parquet import read_parquet

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        return read_parquet(tmp_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


async def list_side_tables(plan_id: UUID, version_no: int) -> dict[str, pl.DataFrame]:
    """Read all side-table snapshot Parquets for a given plan version."""
    storage = get_storage()
    prefix = f"snapshots/{plan_id}/v{version_no}__"
    if hasattr(storage, "list_keys"):
        keys = await storage.list_keys(prefix)
    else:
        keys = []

    result: dict[str, pl.DataFrame] = {}
    from planner.engine.ingest.parquet import read_parquet

    for key in keys:
        filename = key.split("/")[-1]
        table_name = filename.split("__", 1)[1].removesuffix(".parquet")
        data = await storage.get_object(key)
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            result[table_name] = read_parquet(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return result


__all__ = [
    "LocalStorageAdapter",
    "get_current_version_no",
    "get_storage",
    "list_side_tables",
    "read_snapshot_frame",
    "routers",
]
