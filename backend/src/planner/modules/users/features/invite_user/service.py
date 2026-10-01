"""Service logic for the invite_user use case (Backend.md)."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.db import uuid7
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal, hash_token
from planner.modules.users.features.invite_user.schemas import (
    InviteUserRequest,
    InviteUserResponse,
)
from planner.modules.users.models import VALID_ROLES, Invite, User

INVITE_TTL_HOURS = 24
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def invite_user_service(
    session: AsyncSession,
    actor: RequestPrincipal,
    data: InviteUserRequest,
) -> InviteUserResponse:
    """Create a 24 h invite for an email/role and return the raw token once."""
    email_clean = data.email.strip().lower()
    if not _EMAIL_RE.match(email_clean):
        raise AppError("VALIDATION_ERROR", message="Enter a valid email address.")

    # The Role Literal on the request is the primary gate; this guard also covers
    # non-HTTP callers of the service.
    if data.role not in VALID_ROLES:
        raise AppError("VALIDATION_ERROR", message="Unknown role.")

    existing = (
        await session.execute(select(User).where(User.email == email_clean))
    ).scalar_one_or_none()
    if existing is not None and existing.status == "active":
        raise AppError("USER_EXISTS")
    # A user still in "invited" state is re-invited: a fresh token supersedes the
    # previous one when the invitee accepts.

    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=INVITE_TTL_HOURS)

    session.add(
        Invite(
            id=uuid7(),
            email=email_clean,
            role=data.role,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            accepted_at=None,
        )
    )
    await session.commit()

    await record_audit(
            session=session,
        user_id=actor.user_id,
        user_role=actor.role,
        event_type="users.invite",
        object_type="user",
        object_id=email_clean,
        details={"email": email_clean, "role": data.role, "expires_at": expires_at.isoformat()},
    )

    return InviteUserResponse(invite_token=raw_token, expires_at=expires_at)
