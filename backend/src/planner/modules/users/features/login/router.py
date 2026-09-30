"""HTTP router for user login (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import get_session
from planner.modules.users.features.login.schemas import LoginRequest, TokenResponse
from planner.modules.users.features.login.service import login_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate with email and password, returning JWT and setting refresh cookie."""
    result = await login_user(session, payload)
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
