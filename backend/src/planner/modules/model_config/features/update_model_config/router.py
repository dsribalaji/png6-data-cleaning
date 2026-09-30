"""FastAPI router for PUT /model-config."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal, require_roles
from planner.modules.model_config.features.get_model_config.schemas import ModelConfigOut
from planner.modules.model_config.features.update_model_config.schemas import UpdateModelConfigInput
from planner.modules.model_config.features.update_model_config.service import update_model_config

router = APIRouter(prefix="/api/v1/model-config", tags=["model-config"])


# NOTE: require_roles is an auth dependency owned by worker W1
@router.put(
    "",
    response_model=ModelConfigOut,
    dependencies=[Depends(require_roles("administrator"))],
)
@router.put(
    "/",
    response_model=ModelConfigOut,
    dependencies=[Depends(require_roles("administrator"))],
    include_in_schema=False,
)
async def update_model_config_endpoint(
    input: UpdateModelConfigInput,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> ModelConfigOut:
    """Update or initialize the active model configuration."""
    return await update_model_config(
        session,
        input,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
