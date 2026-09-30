"""Service logic for user login (Backend.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.errors import AppError
from planner.core.security import (
    create_access_token,
    new_refresh_token,
    verify_password,
)
from planner.modules.users.features.login.schemas import LoginRequest, LoginResult
from planner.modules.users.models import RefreshToken, User


async def login_user(session: AsyncSession, data: LoginRequest) -> LoginResult:
    """Authenticate user with email/password and issue access + refresh tokens."""
    email_clean = data.email.strip().lower()
    now = datetime.now(timezone.utc)

    stmt = select(User).where(User.email == email_clean)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        await record_audit(
            session=session,
            user_id=None,
            user_role=None,
            event_type="auth.login",
            object_type="user",
            object_id=email_clean,
            details={"reason": "user_not_found", "email": email_clean},
        )
        raise AppError("INVALID_CREDENTIALS")

    role = user.role_rel.role if user.role_rel else "viewer"

    # Check lockout
    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            await record_audit(
            session=session,
                user_id=user.id,
                user_role=role,
                event_type="auth.login",
                object_type="user",
                object_id=str(user.id),
                details={"reason": "account_locked", "email": email_clean},
            )
            raise AppError("ACCOUNT_LOCKED")

    # Check password
    is_valid_pwd = (
        user.password_hash is not None
        and verify_password(data.password, user.password_hash)
    )

    if not is_valid_pwd:
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = now + timedelta(minutes=15)
            await session.commit()
            await record_audit(
            session=session,
                user_id=user.id,
                user_role=role,
                event_type="auth.login",
                object_type="user",
                object_id=str(user.id),
                details={"reason": "account_locked_failed_attempts", "email": email_clean},
            )
            raise AppError("ACCOUNT_LOCKED")

        await session.commit()
        await record_audit(
            session=session,
            user_id=user.id,
            user_role=role,
            event_type="auth.login",
            object_type="user",
            object_id=str(user.id),
            details={
                "reason": "invalid_password",
                "failed_attempts": user.failed_logins,
                "email": email_clean,
            },
        )
        raise AppError("INVALID_CREDENTIALS")

    # Check status
    if user.status != "active":
        await record_audit(
            session=session,
            user_id=user.id,
            user_role=role,
            event_type="auth.login",
            object_type="user",
            object_id=str(user.id),
            details={"reason": "account_inactive", "status": user.status, "email": email_clean},
        )
        raise AppError("ACCOUNT_INACTIVE")

    # Success: reset lockout counters
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now

    # Issue access token
    access_token = create_access_token(user_id=user.id, role=role)

    # Issue refresh token
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

    await record_audit(
            session=session,
        user_id=user.id,
        user_role=role,
        event_type="auth.login",
        object_type="user",
        object_id=str(user.id),
        details={"status": "success", "email": email_clean},
    )

    return LoginResult(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_minutes * 60,
        refresh_token=opaque_refresh,
    )
