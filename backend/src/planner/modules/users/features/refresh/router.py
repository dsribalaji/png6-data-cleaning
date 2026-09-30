"""HTTP router for token refresh (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import get_session
from planner.core.errors import AppError
from planner.modules.users.features.refresh.schemas import TokenResponse
from planner.modules.users.features.refresh.service import refresh_tokens

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh_endpoint(
    response: Response,
    x_requested_with: str | None = Header(None, alias="X-Requested-With"),
    refresh_token: str | None = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Rotate refresh token and issue new access token. Requires X-Requested-With header."""
    if not x_requested_with:
        raise AppError("FORBIDDEN")
    if not refresh_token:
        raise AppError("INVALID_CREDENTIALS")

    result = await refresh_tokens(session, refresh_token)
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
