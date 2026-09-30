"""HTTP router for accepting user invites (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import get_session
from planner.modules.users.features.accept_invite.schemas import (
    AcceptInviteRequest,
    TokenResponse,
)
from planner.modules.users.features.accept_invite.service import accept_invite

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/invites/{token}/accept", response_model=TokenResponse)
async def accept_invite_endpoint(
    token: str,
    payload: AcceptInviteRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Accept invitation, set password, and auto-login."""
    result = await accept_invite(session, token, payload)
    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_days * 86400,
    )
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )
