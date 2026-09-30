"""Service logic for the me use case (Backend.md)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.me.schemas import UserRead
from planner.modules.users.models import User


async def get_me(session: AsyncSession, actor: RequestPrincipal) -> UserRead:
    """Load the current authenticated user; raise ACCOUNT_INACTIVE if not active."""
    stmt = select(User).where(User.id == actor.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or user.status != "active":
        raise AppError("ACCOUNT_INACTIVE")

    role = user.role_rel.role if user.role_rel else actor.role
    return UserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        role=role,
    )
