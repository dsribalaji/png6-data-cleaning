"""Service logic for the deactivate_user use case (Backend.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.deactivate_user.schemas import UserRead
from planner.modules.users.models import RefreshToken, User, UserRole


async def deactivate_user_service(
    session: AsyncSession,
    actor: RequestPrincipal,
    target_id: UUID,
) -> UserRead:
    """Set a user to 'deactivated' and revoke every live refresh token they hold."""
    if target_id == actor.user_id:
        raise AppError("FORBIDDEN")

    user = (
        await session.execute(select(User).where(User.id == target_id))
    ).scalar_one_or_none()
    if user is None:
        raise AppError("NOT_FOUND")

    now = datetime.now(timezone.utc)
    previous_status = user.status
    user.status = "deactivated"

    # Revoke every outstanding refresh token: no session survives deactivation.
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.commit()
    await session.refresh(user)

    await record_audit(
        user_id=actor.user_id,
        user_role=actor.role,
        event_type="users.deactivate",
        object_type="user",
        object_id=str(user.id),
        details={
            "target_user_id": str(user.id),
            "previous_status": previous_status,
            "new_status": "deactivated",
        },
    )

    role_row = (
        await session.execute(select(UserRole.role).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()

    return UserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        role=role_row,
    )
