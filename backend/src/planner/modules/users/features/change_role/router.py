"""HTTP router for the change_role use case (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.users.features.change_role.schemas import (
    ChangeRoleRequest,
    UserRead,
)
from planner.modules.users.features.change_role.service import change_role_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch("/{user_id}/role", response_model=UserRead)
async def change_role_endpoint(
    user_id: UUID,
    payload: ChangeRoleRequest,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("administrator")),
) -> UserRead:
    """Change a user's role (administrator only, never their own)."""
    return await change_role_service(
        session=session,
        actor=principal,
        target_id=user_id,
        data=payload,
    )
