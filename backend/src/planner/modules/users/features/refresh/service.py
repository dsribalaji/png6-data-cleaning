"""Service logic for refresh token rotation and reuse detection (Backend.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.errors import AppError
from planner.core.security import (
    create_access_token,
    hash_token,
    new_refresh_token,
)
from planner.modules.users.features.refresh.schemas import RefreshResult
from planner.modules.users.models import RefreshToken, User


async def refresh_tokens(session: AsyncSession, refresh_token_raw: str) -> RefreshResult:
    """Validate refresh token, rotate it within family, and detect reuse."""
    token_h = hash_token(refresh_token_raw)
    now = datetime.now(timezone.utc)

    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_h)
    result = await session.execute(stmt)
    token_row = result.scalar_one_or_none()

    if token_row is None:
        raise AppError("INVALID_CREDENTIALS")

    # Reuse detection: if this token was already revoked, revoke the whole family!
    if token_row.revoked_at is not None:
        revoke_stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.family_id == token_row.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await session.execute(revoke_stmt)
        await session.commit()
        raise AppError("INVALID_CREDENTIALS")

    # Check expiration
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        token_row.revoked_at = now
        await session.commit()
        raise AppError("INVALID_CREDENTIALS")

    # Check user active status
    user_stmt = select(User).where(User.id == token_row.user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()

    if user is None or user.status != "active":
        raise AppError("ACCOUNT_INACTIVE")

    # Rotate: revoke old token
    token_row.revoked_at = now

    # Issue new token in the SAME family
    new_opaque, new_hash = new_refresh_token()
    new_expires = now + timedelta(days=settings.jwt_refresh_days)
    new_token_row = RefreshToken(
        id=uuid7(),
        user_id=user.id,
        token_hash=new_hash,
        family_id=token_row.family_id,
        expires_at=new_expires,
        revoked_at=None,
    )
    session.add(new_token_row)

    # Issue new access token
    role = user.role_rel.role if user.role_rel else "viewer"
    access_token = create_access_token(user_id=user.id, role=role)

    await session.commit()

    return RefreshResult(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_minutes * 60,
        refresh_token=new_opaque,
    )
