"""Unit tests for the accept_invite feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.security import hash_token, verify_password
from planner.modules.users.features.accept_invite.schemas import AcceptInviteRequest
from planner.modules.users.features.accept_invite.service import accept_invite
from planner.modules.users.models import Invite, RefreshToken, User, UserRole


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as sess:
        yield sess
    await engine.dispose()


@pytest.mark.asyncio
async def test_accept_invite__valid_token__creates_user_and_auto_logs_in(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    raw_token = "raw_invite_token_12345"
    invite = Invite(
        email="newuser@example.com",
        role="data_engineer",
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(hours=24),
        accepted_at=None,
    )
    session.add(invite)
    await session.commit()

    request = AcceptInviteRequest(
        password="MyStrongPassword123!",
        first_name="Charles",
        last_name="Babbage",
    )
    result = await accept_invite(session, raw_token, request)

    assert result.access_token is not None
    assert result.refresh_token is not None

    # Verify user row
    user = (
        await session.execute(select(User).where(User.email == "newuser@example.com"))
    ).scalar_one_or_none()
    assert user is not None
    assert user.status == "active"
    assert user.first_name == "Charles"
    assert user.last_name == "Babbage"
    assert user.password_hash is not None
    assert verify_password("MyStrongPassword123!", user.password_hash)

    # Verify role row
    role = (
        await session.execute(select(UserRole).where(UserRole.user_id == user.id))
    ).scalar_one_or_none()
    assert role is not None
    assert role.role == "data_engineer"

    # Verify invite accepted
    await session.refresh(invite)
    assert invite.accepted_at is not None

    # Verify refresh token created
    tokens = (
        await session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
    ).scalars().all()
    assert len(tokens) == 1


@pytest.mark.asyncio
async def test_accept_invite__existing_invited_user__activates_user_and_sets_password(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    user = User(
        email="precreated@example.com",
        status="invited",
    )
    session.add(user)
    raw_token = "precreated_token_abc"
    invite = Invite(
        email="precreated@example.com",
        role="administrator",
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(hours=24),
        accepted_at=None,
    )
    session.add(invite)
    await session.commit()

    request = AcceptInviteRequest(
        password="AdminPassword1234!",
        first_name="Grace",
        last_name="Hopper",
    )
    result = await accept_invite(session, raw_token, request)

    assert result.access_token is not None

    await session.refresh(user)
    assert user.status == "active"
    assert user.first_name == "Grace"
    assert user.last_name == "Hopper"
    assert verify_password("AdminPassword1234!", user.password_hash)


@pytest.mark.asyncio
async def test_accept_invite__already_accepted_token__raises_invalid_credentials(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    raw_token = "used_token_xyz"
    invite = Invite(
        email="used@example.com",
        role="viewer",
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(hours=24),
        accepted_at=now - timedelta(hours=1),
    )
    session.add(invite)
    await session.commit()

    request = AcceptInviteRequest(password="ValidPassword123!")
    with pytest.raises(AppError) as exc_info:
        await accept_invite(session, raw_token, request)

    assert exc_info.value.code == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_accept_invite__expired_token__raises_invalid_credentials(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    raw_token = "expired_token_xyz"
    invite = Invite(
        email="expired@example.com",
        role="viewer",
        token_hash=hash_token(raw_token),
        expires_at=now - timedelta(minutes=5),
        accepted_at=None,
    )
    session.add(invite)
    await session.commit()

    request = AcceptInviteRequest(password="ValidPassword123!")
    with pytest.raises(AppError) as exc_info:
        await accept_invite(session, raw_token, request)

    assert exc_info.value.code == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_accept_invite__invalid_token__raises_not_found(session: AsyncSession) -> None:
    request = AcceptInviteRequest(password="ValidPassword123!")
    with pytest.raises(AppError) as exc_info:
        await accept_invite(session, "nonexistent_token", request)

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404
