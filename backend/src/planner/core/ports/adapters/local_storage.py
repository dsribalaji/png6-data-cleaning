"""Local filesystem storage adapter (Backend.md, local demo mode).

Files are stored under a local root directory. Pre-signed URLs are returned
as relative paths `/api/v1/files/{key}`, which the FastAPI application serves.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from planner.core.errors import AppError


class LocalStorageAdapter:
    """StoragePort implementation using local filesystem."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Write bytes to key under root directory."""
        path = self.root / key.lstrip("/")
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        """Read bytes from key; raises AppError('NOT_FOUND') if missing."""
        path = self.root / key.lstrip("/")
        exists = await asyncio.to_thread(path.is_file)
        if not exists:
            raise AppError("NOT_FOUND", f"Object not found: {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        """Return an API file-serving path for local downloads."""
        cleaned_key = key.lstrip("/")
        return f"/api/v1/files/{cleaned_key}"

    async def delete(self, key: str) -> None:
        """Delete file at key if it exists."""
        path = self.root / key.lstrip("/")
        if await asyncio.to_thread(path.is_file):
            await asyncio.to_thread(path.unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        """Check if file exists at key."""
        path = self.root / key.lstrip("/")
        return await asyncio.to_thread(path.is_file)

    async def list(self, prefix: str) -> list[str]:
        """List all object keys starting with prefix."""
        prefix_clean = prefix.lstrip("/")

        def _scan() -> list[str]:
            keys: list[str] = []
            for path in self.root.rglob("*"):
                if path.is_file():
                    rel = str(path.relative_to(self.root)).replace("\\", "/")
                    if rel.startswith(prefix_clean):
                        keys.append(rel)
            return sorted(keys)

        return await asyncio.to_thread(_scan)

    # Aliases
    put_object = put
    get_object = get
