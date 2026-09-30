"""HTTP router for the deactivate_user use case (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.users.features.deactivate_user.schemas import UserRead
from planner.modules.users.features.deactivate_user.service import deactivate_user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user_endpoint(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("administrator")),
) -> UserRead:
    """Deactivate a user and revoke their sessions (administrator only, never self)."""
    return await deactivate_user_service(session=session, actor=principal, target_id=user_id)
