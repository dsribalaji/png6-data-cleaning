"""FastAPI router for GET /model-config."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal, require_roles
from planner.modules.model_config.features.get_model_config.schemas import ModelConfigOut
from planner.modules.model_config.features.get_model_config.service import get_model_config

router = APIRouter(prefix="/api/v1/model-config", tags=["model-config"])


# NOTE: require_roles is an auth dependency owned by worker W1
@router.get(
    "",
    response_model=ModelConfigOut,
    dependencies=[Depends(require_roles("administrator"))],
)
@router.get(
    "/",
    response_model=ModelConfigOut,
    dependencies=[Depends(require_roles("administrator"))],
    include_in_schema=False,
)
async def get_model_config_endpoint(
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> ModelConfigOut:
    """Get the currently active model configuration."""
    return await get_model_config(
        session,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
