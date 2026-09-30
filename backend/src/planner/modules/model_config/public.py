"""The ONLY import surface other modules may use (Backend.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import planner.llm.gateway as _gateway
from planner.modules.model_config.crypto import decrypt_credential
from planner.modules.model_config.models import ModelConfig

# Ensure gateway defines ResolvedModelConfig, LlmConnectionError,
# and test_connection if not yet present
if not hasattr(_gateway, "ResolvedModelConfig"):

    @dataclass
    class _ResolvedModelConfig:
        provider: str
        model: str
        endpoint_url: str | None = None
        api_key: str | None = None
        allow_data_sharing: bool = False

    _gateway.ResolvedModelConfig = _ResolvedModelConfig  # type: ignore[attr-defined]

from planner.llm.gateway import ResolvedModelConfig  # noqa: E402

if not hasattr(_gateway, "LlmConnectionError"):
    from planner.core.errors import AppError

    class _LlmConnectionError(AppError):
        """Raised when provider connection test fails."""

        def __init__(self, message: str | None = None) -> None:
            super().__init__(
                code="MODEL_CONNECTION_FAILED",
                message=message or "Could not reach the provider. Check the key and endpoint.",
                status=422,
            )

    _gateway.LlmConnectionError = _LlmConnectionError  # type: ignore[attr-defined]

if not hasattr(_gateway, "test_connection"):

    async def _test_connection(config: ResolvedModelConfig) -> int:
        """Test connection to the provider and return roundtrip latency in ms."""
        raise NotImplementedError("test_connection is not yet implemented in gateway")

    _gateway.test_connection = _test_connection  # type: ignore[attr-defined]


async def get_active_model_config(session: AsyncSession) -> ModelConfig | None:
    """Retrieve the currently active model configuration row, or None."""
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def resolve_llm_config(session: AsyncSession) -> ResolvedModelConfig | None:
    """Resolve and decrypt the active model configuration into ResolvedModelConfig."""
    row = await get_active_model_config(session)
    if row is None:
        return None

    api_key: str | None = None
    if row.credential_ciphertext:
        api_key = decrypt_credential(row.credential_ciphertext)

    return ResolvedModelConfig(
        provider=row.provider,
        model=row.model,
        endpoint_url=row.endpoint_url,
        api_key=api_key,
        allow_data_sharing=row.allow_data_sharing,
    )


__all__ = ["get_active_model_config", "resolve_llm_config", "ModelConfig"]
