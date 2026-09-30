"""FastAPI router for POST /model-config/test."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal, require_roles
from planner.modules.model_config.features.test_model_connection.schemas import (
    TestModelConnectionInput,
    TestModelConnectionOut,
)
from planner.modules.model_config.features.test_model_connection.service import (
    test_model_connection,
)

router = APIRouter(prefix="/api/v1/model-config", tags=["model-config"])


# NOTE: require_roles is an auth dependency owned by worker W1
@router.post(
    "/test",
    response_model=TestModelConnectionOut,
    dependencies=[Depends(require_roles("administrator"))],
)
@router.post(
    "/test/",
    response_model=TestModelConnectionOut,
    dependencies=[Depends(require_roles("administrator"))],
    include_in_schema=False,
)
async def test_model_connection_endpoint(
    input: TestModelConnectionInput | None = None,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> TestModelConnectionOut:
    """Test connection to the active LLM provider or with provided overrides."""
    return await test_model_connection(
        session,
        input,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
