"""HTTP router for the invite_user use case (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.users.features.invite_user.schemas import (
    InviteUserRequest,
    InviteUserResponse,
)
from planner.modules.users.features.invite_user.service import invite_user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("/invites", response_model=InviteUserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user_endpoint(
    payload: InviteUserRequest,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("administrator")),
) -> InviteUserResponse:
    """Invite a user by email with a role (administrator only).

    TODO: the raw token is returned in the response body exactly once. Production
    must email it to the invitee (no email provider is wired in this build) and
    stop returning it here; only the sha256 hash is persisted.
    """
    return await invite_user_service(session=session, actor=principal, data=payload)
