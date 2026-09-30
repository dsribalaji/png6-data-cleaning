"""Service logic for accepting user invites (Backend.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.errors import AppError, app_error
from planner.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
)
from planner.modules.users.features.accept_invite.schemas import (
    AcceptInviteRequest,
    AcceptInviteResult,
)
from planner.modules.users.models import Invite, RefreshToken, User, UserRole


async def accept_invite(
    session: AsyncSession,
    token: str,
    data: AcceptInviteRequest,
) -> AcceptInviteResult:
    """Validate invite token, activate user with password, and issue login credentials."""
    token_h = hash_token(token)
    now = datetime.now(timezone.utc)

    stmt = select(Invite).where(Invite.token_hash == token_h)
    result = await session.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise app_error("NOT_FOUND")

    if invite.accepted_at is not None:
        raise AppError("INVALID_CREDENTIALS", message="Invite has already been accepted.")

    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise AppError("INVALID_CREDENTIALS", message="Invite has expired.")

    email_clean = invite.email.strip().lower()
    pwd_hash = hash_password(data.password)

    user_stmt = select(User).where(User.email == email_clean)
    user = (await session.execute(user_stmt)).scalar_one_or_none()

    if user is None:
        user = User(
            id=uuid7(),
            email=email_clean,
            first_name=data.first_name,
            last_name=data.last_name,
            password_hash=pwd_hash,
            status="active",
        )
        session.add(user)
        await session.flush()
    else:
        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        user.password_hash = pwd_hash
        user.status = "active"

    role_stmt = select(UserRole).where(UserRole.user_id == user.id)
    user_role = (await session.execute(role_stmt)).scalar_one_or_none()
    if user_role is None:
        user_role = UserRole(user_id=user.id, role=invite.role)
        session.add(user_role)
    else:
        user_role.role = invite.role

    invite.accepted_at = now

    # Auto-login: issue access token and refresh token
    access_token = create_access_token(user_id=user.id, role=invite.role)
    opaque_refresh, refresh_hash = new_refresh_token()
    family_id = uuid7()
    refresh_expires = now + timedelta(days=settings.jwt_refresh_days)

    rt = RefreshToken(
        id=uuid7(),
        user_id=user.id,
        token_hash=refresh_hash,
        family_id=family_id,
        expires_at=refresh_expires,
        revoked_at=None,
    )
    session.add(rt)
    await session.commit()

    return AcceptInviteResult(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_minutes * 60,
        refresh_token=opaque_refresh,
    )
