"""Unit tests for the refresh feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.errors import AppError
from planner.core.security import hash_token
from planner.modules.users.features.refresh.service import refresh_tokens
from planner.modules.users.models import RefreshToken, User, UserRole


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
async def test_refresh__valid_token__rotates_token_in_same_family(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    user = User(email="active@example.com", status="active")
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role="data_engineer"))

    family_id = uuid7()
    raw_token = "valid_opaque_token_string_12345"
    old_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=family_id,
        expires_at=now + timedelta(days=7),
        revoked_at=None,
    )
    session.add(old_token)
    await session.commit()

    result = await refresh_tokens(session, raw_token)

    assert result.access_token is not None
    assert result.refresh_token != raw_token

    # Verify old token is now revoked
    await session.refresh(old_token)
    assert old_token.revoked_at is not None

    # Verify new token exists with same family_id
    new_token = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(result.refresh_token))
        )
    ).scalar_one_or_none()
    assert new_token is not None
    assert new_token.family_id == family_id
    assert new_token.revoked_at is None


@pytest.mark.asyncio
async def test_refresh__revoked_token_reuse__revokes_entire_family_and_raises_invalid_credentials(
    session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc)
    user = User(email="reuse@example.com", status="active")
    session.add(user)
    await session.flush()

    family_id = uuid7()
    compromised_raw = "compromised_token_already_revoked"
    t1 = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(compromised_raw),
        family_id=family_id,
        expires_at=now + timedelta(days=7),
        revoked_at=now - timedelta(minutes=5),  # already revoked
    )
    t2 = RefreshToken(
        user_id=user.id,
        token_hash=hash_token("active_token_in_same_family"),
        family_id=family_id,
        expires_at=now + timedelta(days=7),
        revoked_at=None,
    )
    session.add_all([t1, t2])
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await refresh_tokens(session, compromised_raw)

    assert exc_info.value.code == "INVALID_CREDENTIALS"

    # Entire family should now be revoked
    await session.refresh(t2)
    assert t2.revoked_at is not None


@pytest.mark.asyncio
async def test_refresh__expired_token__raises_invalid_credentials(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    user = User(email="expired@example.com", status="active")
    session.add(user)
    await session.flush()

    raw_token = "expired_raw_token"
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid7(),
        expires_at=now - timedelta(minutes=1),
        revoked_at=None,
    )
    session.add(token)
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await refresh_tokens(session, raw_token)

    assert exc_info.value.code == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh__deactivated_user__raises_account_inactive(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    user = User(email="deact@example.com", status="deactivated")
    session.add(user)
    await session.flush()

    raw_token = "token_for_deactivated_user"
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid7(),
        expires_at=now + timedelta(days=7),
        revoked_at=None,
    )
    session.add(token)
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await refresh_tokens(session, raw_token)

    assert exc_info.value.code == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_refresh__unknown_token__raises_invalid_credentials(session: AsyncSession) -> None:
    with pytest.raises(AppError) as exc_info:
        await refresh_tokens(session, "completely_unknown_token")

    assert exc_info.value.code == "INVALID_CREDENTIALS"
