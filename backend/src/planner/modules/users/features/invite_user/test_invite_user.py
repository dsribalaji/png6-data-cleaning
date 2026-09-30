"""Unit tests for the invite_user feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal, hash_token
from planner.modules.users.features.invite_user.schemas import InviteUserRequest
from planner.modules.users.features.invite_user.service import invite_user_service
from planner.modules.users.models import Invite, User


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


def _actor() -> RequestPrincipal:
    return RequestPrincipal(user_id=uuid4(), role="administrator")


@pytest.mark.asyncio
async def test_invite_user__new_email__stores_hashed_token_and_returns_raw_token(
    session: AsyncSession,
) -> None:
    result = await invite_user_service(
        session,
        _actor(),
        InviteUserRequest(email="New.User@Example.com", role="data_engineer"),
    )

    assert result.invite_token

    invites = (await session.execute(select(Invite))).scalars().all()
    assert len(invites) == 1
    invite = invites[0]
    assert invite.email == "new.user@example.com"
    assert invite.role == "data_engineer"
    assert invite.accepted_at is None
    # Only the sha256 hash is persisted; the raw token is never stored.
    assert invite.token_hash == hash_token(result.invite_token)
    assert result.invite_token not in invite.token_hash


@pytest.mark.asyncio
async def test_invite_user__valid_email__expires_in_24_hours(session: AsyncSession) -> None:
    before = datetime.now(timezone.utc)

    result = await invite_user_service(
        session,
        _actor(),
        InviteUserRequest(email="timing@example.com", role="viewer"),
    )

    after = datetime.now(timezone.utc)
    assert before + timedelta(hours=24) <= result.expires_at <= after + timedelta(hours=24)

    invites = (await session.execute(select(Invite))).scalars().all()
    row_expiry = invites[0].expires_at
    assert row_expiry is not None
    if row_expiry.tzinfo is None:
        row_expiry = row_expiry.replace(tzinfo=timezone.utc)
    # The persisted expiry matches the value returned to the caller.
    assert abs((row_expiry - result.expires_at).total_seconds()) < 1


@pytest.mark.asyncio
async def test_invite_user__existing_active_user__raises_user_exists(session: AsyncSession) -> None:
    session.add(User(email="taken@example.com", status="active"))
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await invite_user_service(
            session,
            _actor(),
            InviteUserRequest(email="TAKEN@example.com", role="viewer"),
        )

    assert exc_info.value.code == "USER_EXISTS"
    assert exc_info.value.status == 409
    assert (await session.execute(select(Invite))).scalars().all() == []


@pytest.mark.asyncio
async def test_invite_user__existing_invited_user__issues_second_invite(
    session: AsyncSession,
) -> None:
    session.add(User(email="pending@example.com", status="invited"))
    await session.commit()

    result = await invite_user_service(
        session,
        _actor(),
        InviteUserRequest(email="pending@example.com", role="auditor"),
    )

    assert result.invite_token
    invites = (await session.execute(select(Invite))).scalars().all()
    assert len(invites) == 1
    assert invites[0].role == "auditor"


@pytest.mark.asyncio
async def test_invite_user__malformed_email__raises_validation_error(session: AsyncSession) -> None:
    with pytest.raises(AppError) as exc_info:
        await invite_user_service(
            session,
            _actor(),
            InviteUserRequest(email="not-an-email", role="viewer"),
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status == 422
    assert (await session.execute(select(Invite))).scalars().all() == []


@pytest.mark.asyncio
async def test_invite_user__two_invites__tokens_differ(session: AsyncSession) -> None:
    first = await invite_user_service(
        session, _actor(), InviteUserRequest(email="one@example.com", role="viewer")
    )
    second = await invite_user_service(
        session, _actor(), InviteUserRequest(email="two@example.com", role="viewer")
    )

    assert first.invite_token != second.invite_token
    assert len((await session.execute(select(Invite))).scalars().all()) == 2
