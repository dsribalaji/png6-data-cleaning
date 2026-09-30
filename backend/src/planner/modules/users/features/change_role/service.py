"""Service logic for the change_role use case (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.change_role.schemas import (
    ChangeRoleRequest,
    UserRead,
)
from planner.modules.users.models import VALID_ROLES, User, UserRole


async def change_role_service(
    session: AsyncSession,
    actor: RequestPrincipal,
    target_id: UUID,
    data: ChangeRoleRequest,
) -> UserRead:
    """Replace a user's single role; an administrator cannot change their own."""
    if target_id == actor.user_id:
        raise AppError("FORBIDDEN")

    # The Role Literal on the request is the primary gate; this guard also covers
    # non-HTTP callers of the service.
    if data.role not in VALID_ROLES:
        raise AppError("VALIDATION_ERROR", message="Unknown role.")

    user = (
        await session.execute(select(User).where(User.id == target_id))
    ).scalar_one_or_none()
    if user is None:
        raise AppError("NOT_FOUND")

    role_row = (
        await session.execute(select(UserRole).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()

    previous_role = role_row.role if role_row is not None else None
    if role_row is None:
        session.add(UserRole(user_id=user.id, role=data.role))
    else:
        role_row.role = data.role

    await session.commit()
    await session.refresh(user)

    await record_audit(
            session=session,
        user_id=actor.user_id,
        user_role=actor.role,
        event_type="users.role_change",
        object_type="user",
        object_id=str(user.id),
        details={
            "target_user_id": str(user.id),
            "previous_role": previous_role,
            "new_role": data.role,
        },
    )

    return UserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        role=data.role,
    )
