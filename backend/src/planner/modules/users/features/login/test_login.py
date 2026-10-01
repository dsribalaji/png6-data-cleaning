"""Unit tests for the login feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.security import hash_password
from planner.modules.users.features.login.schemas import LoginRequest
from planner.modules.users.features.login.service import login_user
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
async def test_login__valid_credentials__returns_tokens(session: AsyncSession) -> None:
    user = User(
        email="engineer@example.com",
        password_hash=hash_password("SuperSecret123!"),
        status="active",
    )
    session.add(user)
    await session.flush()
    role = UserRole(user_id=user.id, role="data_engineer")
    session.add(role)
    await session.commit()

    request = LoginRequest(email="ENGINEER@example.com", password="SuperSecret123!")
    result = await login_user(session, request)

    assert result.access_token is not None
    assert result.token_type == "Bearer"
    assert result.expires_in == 15 * 60
    assert result.refresh_token is not None

    # Check refresh token persisted in DB
    tokens = (await session.execute(select(RefreshToken))).scalars().all()
    assert len(tokens) == 1
    assert tokens[0].user_id == user.id


@pytest.mark.asyncio
async def test_login__wrong_password__increments_failed_logins_and_raises_invalid_credentials(
    session: AsyncSession,
) -> None:
    user = User(
        email="user@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        status="active",
        failed_logins=0,
    )
    session.add(user)
    await session.commit()

    request = LoginRequest(email="user@example.com", password="WrongPassword!")
    with pytest.raises(AppError) as exc_info:
        await login_user(session, request)

    assert exc_info.value.code == "INVALID_CREDENTIALS"

    await session.refresh(user)
    assert user.failed_logins == 1
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_login__five_failed_attempts__locks_account_for_15_minutes(
    session: AsyncSession,
) -> None:
    user = User(
        email="locked@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        status="active",
        failed_logins=4,
    )
    session.add(user)
    await session.commit()

    request = LoginRequest(email="locked@example.com", password="WrongPassword!")
    with pytest.raises(AppError) as exc_info:
        await login_user(session, request)

    assert exc_info.value.code == "ACCOUNT_LOCKED"
    assert exc_info.value.status == 423

    await session.refresh(user)
    assert user.failed_logins == 5
    assert user.locked_until is not None


@pytest.mark.asyncio
async def test_login__locked_account__raises_account_locked(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    user = User(
        email="already_locked@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        status="active",
        failed_logins=5,
        locked_until=now + timedelta(minutes=10),
    )
    session.add(user)
    await session.commit()

    request = LoginRequest(email="already_locked@example.com", password="CorrectPassword123!")
    with pytest.raises(AppError) as exc_info:
        await login_user(session, request)

    assert exc_info.value.code == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_login__inactive_user__raises_account_inactive(session: AsyncSession) -> None:
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("CorrectPassword123!"),
        status="deactivated",
    )
    session.add(user)
    await session.commit()

    request = LoginRequest(email="inactive@example.com", password="CorrectPassword123!")
    with pytest.raises(AppError) as exc_info:
        await login_user(session, request)

    assert exc_info.value.code == "ACCOUNT_INACTIVE"
    assert exc_info.value.status == 403


@pytest.mark.asyncio
async def test_login__nonexistent_user__raises_invalid_credentials(session: AsyncSession) -> None:
    request = LoginRequest(email="unknown@example.com", password="SomePassword123!")
    with pytest.raises(AppError) as exc_info:
        await login_user(session, request)

    assert exc_info.value.code == "INVALID_CREDENTIALS"
