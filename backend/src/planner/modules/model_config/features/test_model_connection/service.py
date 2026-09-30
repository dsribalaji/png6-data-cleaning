"""Service for testing model connection."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import planner.llm.gateway as gateway
from planner.core.audit import record_audit
from planner.modules.model_config.crypto import decrypt_credential
from planner.modules.model_config.errors import (
    MODEL_CONFIG_NOT_FOUND,
    MODEL_CONNECTION_FAILED,
)
from planner.modules.model_config.features.test_model_connection.schemas import (
    TestModelConnectionInput,
    TestModelConnectionOut,
)
from planner.modules.model_config.models import ModelConfig
from planner.modules.model_config.public import ResolvedModelConfig


if not hasattr(gateway, "LlmConnectionError"):

    class _LlmConnectionError(AppError):
        """Raised when provider connection test fails."""

        def __init__(self, message: str | None = None) -> None:
            super().__init__(
                code="MODEL_CONNECTION_FAILED",
                message=message or "Could not reach the provider. Check the key and endpoint.",
                status=422,
            )

    gateway.LlmConnectionError = _LlmConnectionError  # type: ignore[attr-defined]


async def test_model_connection(
    session: AsyncSession,
    input: TestModelConnectionInput | None = None,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> TestModelConnectionOut:
    """Test connection to the active LLM provider or with provided overrides.

    Raises:
        AppError: MODEL_CONFIG_NOT_FOUND (404) if no active configuration exists
            and no overrides are given.
        LlmConnectionError / AppError: MODEL_CONNECTION_FAILED (422) if connection test fails.
    """
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    result = await session.execute(stmt)
    active_row = result.scalar_one_or_none()

    # Determine provider & model
    provider = (
        input.provider
        if (input and input.provider)
        else (active_row.provider if active_row else None)
    )
    model = (
        input.model
        if (input and input.model)
        else (active_row.model if active_row else None)
    )

    if not provider or not model:
        raise MODEL_CONFIG_NOT_FOUND

    # Determine endpoint_url
    if input and input.endpoint_url is not None:
        endpoint_url = input.endpoint_url
    elif active_row:
        endpoint_url = active_row.endpoint_url
    else:
        endpoint_url = None

    # Determine credential / api_key
    if input and input.credential is not None:
        api_key = input.credential
    elif active_row and active_row.credential_ciphertext:
        api_key = decrypt_credential(active_row.credential_ciphertext)
    else:
        api_key = None

    allow_data_sharing = active_row.allow_data_sharing if active_row else False

    config = ResolvedModelConfig(
        provider=provider,
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
        allow_data_sharing=allow_data_sharing,
    )

    try:
        latency_ms = await gateway.test_connection(config)
    except gateway.LlmConnectionError:
        raise
    except Exception as exc:
        raise MODEL_CONNECTION_FAILED from exc

    # NOTE: record_audit is currently a not-started stub owned by worker W1; wired per specification
    await record_audit(
        user_id=actor_id,
        user_role=actor_role,
        event_type="model_config.tested",
        object_type="model_config",
        object_id=str(active_row.id) if active_row else "ephemeral",
        details={
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
        },
    )

    return TestModelConnectionOut(ok=True, latency_ms=int(latency_ms))


test_model_connection.__test__ = False  # type: ignore[attr-defined]
