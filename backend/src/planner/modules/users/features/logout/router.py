"""HTTP router for user logout (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.users.features.logout.schemas import LogoutResponse
from planner.modules.users.features.logout.service import logout_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/logout", response_model=LogoutResponse)
async def logout_endpoint(
    response: Response,
    refresh_token: str | None = Cookie(None, alias="refresh_token"),
    principal: RequestPrincipal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> LogoutResponse:
    """Revoke active refresh token, clear cookie, and terminate session."""
    result = await logout_user(session, principal, refresh_token)
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return result
