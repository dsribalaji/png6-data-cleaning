"""HTTP router for the me use case (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.users.features.me.schemas import UserRead
from planner.modules.users.features.me.service import get_me

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
async def me_endpoint(
    principal: RequestPrincipal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Return profile for the currently authenticated user."""
    return await get_me(session=session, actor=principal)
