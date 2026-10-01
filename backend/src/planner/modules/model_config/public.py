"""The ONLY import surface other modules may use (Backend.md)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import SessionLocal
from planner.llm.gateway import LlmGateway, ResolvedModelConfig, resolve_env_config
from planner.llm.cache import LlmCache
from planner.modules.model_config.crypto import decrypt_credential
from planner.modules.model_config.models import ModelConfig


async def get_active_model_config(session: AsyncSession) -> ModelConfig | None:
    """Retrieve the currently active model configuration row, or None."""
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_model_config(session: AsyncSession, config_id: object) -> ModelConfig | None:
    """Retrieve one model configuration by id, or None if it does not exist.

    Lets other modules validate a caller-supplied model config id instead of
    letting the database raise a foreign-key violation.
    """
    from uuid import UUID

    stmt = select(ModelConfig).where(ModelConfig.id == UUID(str(config_id)))
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


async def resolve_active_llm_config() -> ResolvedModelConfig | None:
    """The model the Administrator saved in Model settings (FR-049), else env vars."""
    async with SessionLocal() as session:
        config = await resolve_llm_config(session)
    return config if config is not None else await resolve_env_config()


def build_llm_gateway() -> LlmGateway:
    """The one way pipeline tasks get an LLM gateway: saved config + Redis cache (7-day TTL)."""
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=2
        )
    except Exception:  # no redis package: the cache falls back to memory
        redis_client = None
    return LlmGateway(config_resolver=resolve_active_llm_config, cache=LlmCache(redis_client))


def describe_llm_outcome(exc: BaseException | None) -> tuple[str, str | None]:
    """(ai_status, ai_message) for a pipeline step that tried the LLM (Level 3 B2)."""
    if exc is None:
        return "used", None
    code = getattr(exc, "code", None)
    if code == "LLM_NO_CREDENTIAL":
        return "off", "No AI model is configured; only deterministic rules were used."
    first_line = (str(exc).strip().splitlines() or [""])[0][:160]
    message = getattr(exc, "message", None) or f"{type(exc).__name__}: {first_line}"
    return "failed", f"AI suggestions unavailable ({message}); deterministic rules were used."


from planner.modules.model_config.features.get_model_config.router import (  # noqa: E402
    router as get_model_config_router,
)
from planner.modules.model_config.features.list_providers.router import (  # noqa: E402
    router as list_providers_router,
)
from planner.modules.model_config.features.test_model_connection.router import (  # noqa: E402
    router as test_model_connection_router,
)
from planner.modules.model_config.features.update_model_config.router import (  # noqa: E402
    router as update_model_config_router,
)

# Static /providers and /test before any parameterised path.
routers = [
    list_providers_router,
    test_model_connection_router,
    get_model_config_router,
    update_model_config_router,
]

__all__ = [
    "ModelConfig",
    "build_llm_gateway",
    "describe_llm_outcome",
    "get_active_model_config",
    "get_model_config",
    "resolve_active_llm_config",
    "resolve_llm_config",
    "routers",
]
