"""Storage port (MinIO/S3 or local filesystem behind an interface, Backend.md)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

RAW_PREFIX = "raw/"
SNAPSHOTS_PREFIX = "snapshots/"
QUARANTINE_PREFIX = "quarantine/"
EXPORTS_PREFIX = "exports/"
PIPELINES_PREFIX = "pipelines/"
TESTS_PREFIX = "tests/"


class StoragePort(Protocol):
    """Abstract object storage port."""

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Write bytes to the storage key."""
        ...

    async def get(self, key: str) -> bytes:
        """Read bytes from the storage key (raises AppError NOT_FOUND if missing)."""
        ...

    async def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        """Generate a pre-signed download URL (default 15 minutes)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete an object by key."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if an object exists at the specified key."""
        ...

    async def list(self, prefix: str) -> list[str]:
        """List object keys starting with the given prefix."""
        ...

    async def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Alias for put."""
        ...

    async def get_object(self, key: str) -> bytes:
        """Alias for get."""
        ...


def raw_key(dataset_id: UUID, file_name: str) -> str:
    """Format key for raw uploaded file: raw/{dataset_id}/{file_name}."""
    return f"raw/{dataset_id}/{file_name}"


def export_key(plan_id: UUID, version_no: int, table: str, ext: str) -> str:
    """Format key for export file: exports/{plan_id}/v{version_no}/{table}.{ext}."""
    cleaned_ext = ext.lstrip(".")
    return f"exports/{plan_id}/v{version_no}/{table}.{cleaned_ext}"


def snapshot_key(plan_id: UUID, version_no: int) -> str:
    """Format key for parquet snapshot: snapshots/{plan_id}/v{version_no}.parquet."""
    return f"snapshots/{plan_id}/v{version_no}.parquet"
