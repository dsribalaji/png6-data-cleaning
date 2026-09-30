"""Concrete port adapters (boto3 storage, filesystem storage, system clock)."""

from __future__ import annotations

from planner.core.config import settings
from planner.core.ports.adapters.local_storage import LocalStorageAdapter
from planner.core.ports.adapters.s3_storage import S3StorageAdapter
from planner.core.ports.adapters.system_clock import SystemClock
from planner.core.ports.clock import ClockPort
from planner.core.ports.storage import StoragePort

_storage: StoragePort | None = None
_clock: ClockPort | None = None


def get_storage() -> StoragePort:
    """Return configured StoragePort adapter (local filesystem or S3/MinIO)."""
    global _storage
    if _storage is not None:
        return _storage

    if settings.storage_backend == "s3":
        _storage = S3StorageAdapter(
            endpoint_url=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    else:
        _storage = LocalStorageAdapter(root=settings.storage_local_root)
    return _storage


def get_clock() -> ClockPort:
    """Return configured ClockPort adapter (SystemClock)."""
    global _clock
    if _clock is not None:
        return _clock
    _clock = SystemClock()
    return _clock


__all__ = [
    "ClockPort",
    "LocalStorageAdapter",
    "S3StorageAdapter",
    "StoragePort",
    "SystemClock",
    "get_clock",
    "get_storage",
]
