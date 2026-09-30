"""The ONLY import surface other modules may use (Backend.md).

Other modules import from here and never from ``models.py`` or ``features/`` of
this module (import-linter boundary).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.users.features.accept_invite.router import (
    router as accept_invite_router,
)
from planner.modules.users.features.change_role.router import router as change_role_router
from planner.modules.users.features.deactivate_user.router import (
    router as deactivate_user_router,
)
from planner.modules.users.features.invite_user.router import router as invite_user_router
from planner.modules.users.features.list_users.router import router as list_users_router
from planner.modules.users.features.login.router import router as login_router
from planner.modules.users.features.logout.router import router as logout_router
from planner.modules.users.features.me.router import router as me_router
from planner.modules.users.features.me.schemas import UserRead
from planner.modules.users.features.refresh.router import router as refresh_router
from planner.modules.users.models import User, UserRole

# Canonical router order per the Backend.md REST table.
routers: list[APIRouter] = [
    login_router,
    refresh_router,
    logout_router,
    me_router,
    accept_invite_router,
    list_users_router,
    invite_user_router,
    change_role_router,
    deactivate_user_router,
]


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> UserRead:
    """Load the authenticated user with their role; raise ACCOUNT_INACTIVE if not active."""
    user = (
        await session.execute(select(User).where(User.id == principal.user_id))
    ).scalar_one_or_none()

    if user is None or user.status != "active":
        raise AppError("ACCOUNT_INACTIVE")

    role_row = (
        await session.execute(select(UserRole.role).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()

    return UserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        role=role_row if role_row is not None else principal.role,
    )


async def get_user_role(user_id: UUID, session: AsyncSession) -> str | None:
    """Return the single role for a user, or None when no role row exists."""
    return (
        await session.execute(select(UserRole.role).where(UserRole.user_id == user_id))
    ).scalar_one_or_none()


__all__ = ["User", "UserRead", "get_current_user", "get_user_role", "routers"]
