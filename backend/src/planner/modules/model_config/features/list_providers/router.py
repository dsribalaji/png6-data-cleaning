"""FastAPI router for GET /model-config/providers."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal, require_roles
from planner.modules.model_config.features.list_providers.schemas import ProviderInfoOut
from planner.modules.model_config.features.list_providers.service import list_providers

router = APIRouter(prefix="/api/v1/model-config", tags=["model-config"])


# NOTE: require_roles is an auth dependency owned by worker W1
@router.get(
    "/providers",
    response_model=list[ProviderInfoOut],
    dependencies=[Depends(require_roles("administrator"))],
)
@router.get(
    "/providers/",
    response_model=list[ProviderInfoOut],
    dependencies=[Depends(require_roles("administrator"))],
    include_in_schema=False,
)
async def list_providers_endpoint(
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> list[ProviderInfoOut]:
    """List supported LLM providers and their metadata."""
    return await list_providers(
        session,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
