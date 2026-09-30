"""Unit tests for the logout feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.security import RequestPrincipal, hash_token
from planner.modules.users.features.logout.service import logout_user
from planner.modules.users.models import RefreshToken, User


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
async def test_logout__with_valid_refresh_token__revokes_token(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    user = User(email="logout_user@example.com", status="active")
    session.add(user)
    await session.flush()

    raw_token = "valid_opaque_refresh_to_revoke"
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid7(),
        expires_at=now + timedelta(days=7),
        revoked_at=None,
    )
    session.add(token)
    await session.commit()

    principal = RequestPrincipal(user_id=user.id, role="data_engineer")
    result = await logout_user(session, principal, raw_token)

    assert result.message == "Logged out successfully"

    await session.refresh(token)
    assert token.revoked_at is not None


@pytest.mark.asyncio
async def test_logout__without_cookie__succeeds_gracefully(session: AsyncSession) -> None:
    user = User(email="logout_empty@example.com", status="active")
    session.add(user)
    await session.commit()

    principal = RequestPrincipal(user_id=user.id, role="data_engineer")
    result = await logout_user(session, principal, None)

    assert result.message == "Logged out successfully"
