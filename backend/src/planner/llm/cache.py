"""Redis cache for LLM responses (Backend.md, FR-048).

Stores LLM outputs keyed by sha256(provider|model|prompt_version|payload) with a 7-day TTL.
Falls back to in-memory caching with timestamps when Redis is unavailable.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TTL_S = 604800  # 7 days in seconds


class LlmCache:
    """Redis-backed cache for LLM completions with transparent in-memory fallback."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._memory: dict[str, tuple[str, float]] = {}

    def make_key(
        self,
        provider: str,
        model: str,
        prompt_version: str,
        payload_json: str,
    ) -> str:
        """Compute deterministic cache key: llm:{sha256(provider|model|version|payload)}."""
        raw = f"{provider}|{model}|{prompt_version}|{payload_json}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"llm:{digest}"

    async def get(self, key: str) -> str | None:
        """Fetch cached completion string. Returns None on cache miss or error."""
        if self._redis is not None:
            try:
                res = self._redis.get(key)
                if inspect.isawaitable(res):
                    res = await res
                if res is not None:
                    if isinstance(res, bytes):
                        return res.decode("utf-8")
                    return str(res)
            except Exception as exc:  # noqa: BLE001 -- cache never raises; falls back to memory
                logger.warning("llm_cache_redis_get_failed", key=key, error=str(exc))

        # Check in-memory fallback
        item = self._memory.get(key)
        if item is not None:
            val, expires_at = item
            if time.monotonic() < expires_at:
                return val
            # Evict expired entry
            self._memory.pop(key, None)
        return None

    async def set(self, key: str, value: str, ttl_s: float = DEFAULT_TTL_S) -> None:
        """Store completion in cache with TTL. Never raises on Redis errors."""
        if self._redis is not None:
            try:
                px = max(1, int(ttl_s * 1000))
                res = self._redis.set(key, value, px=px)
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:  # noqa: BLE001 -- cache never raises; falls back to memory
                logger.warning("llm_cache_redis_set_failed", key=key, error=str(exc))

        # Always maintain in-memory fallback
        self._memory[key] = (value, time.monotonic() + ttl_s)
