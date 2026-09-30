"""Service for retrieving the active model configuration."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.model_config.errors import MODEL_CONFIG_NOT_FOUND
from planner.modules.model_config.features.get_model_config.schemas import ModelConfigOut
from planner.modules.model_config.models import ModelConfig


async def get_model_config(
    session: AsyncSession,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> ModelConfigOut:
    """Retrieve the active model configuration.

    Raises:
        AppError: MODEL_CONFIG_NOT_FOUND (404) if no configuration has been created yet.
    """
    stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise MODEL_CONFIG_NOT_FOUND

    return ModelConfigOut.model_validate(row)
