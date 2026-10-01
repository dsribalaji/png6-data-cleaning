"""Service logic for the me use case (Backend.md)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.me.schemas import UserRead
from planner.modules.users.models import User, UserRole


async def get_me(session: AsyncSession, actor: RequestPrincipal) -> UserRead:
    """Load the current authenticated user; raise ACCOUNT_INACTIVE if not active."""
    stmt = select(User).where(User.id == actor.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None and settings.auth_mode == "oidc":
        # SSO users exist in Keycloak first; their first call here creates the local
        # row (same id as the token's `sub`) so audit and ownership fields resolve.
        user = User(
            id=actor.user_id,
            email=actor.email or f"{actor.user_id}@sso.local",
            status="active",
        )
        session.add(user)
        session.add(UserRole(user_id=actor.user_id, role=actor.role))
        await session.commit()
        await session.refresh(user, ["role_rel"])

    if user is None or user.status != "active":
        raise AppError("ACCOUNT_INACTIVE")

    # Under SSO, Keycloak owns roles: report the token's, not a stale local copy.
    if settings.auth_mode == "oidc" or not user.role_rel:
        role = actor.role
    else:
        role = user.role_rel.role
    return UserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        role=role,
    )
