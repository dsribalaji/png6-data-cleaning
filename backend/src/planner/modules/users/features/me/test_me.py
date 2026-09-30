"""Unit tests for the me feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.me.service import get_me
from planner.modules.users.models import User, UserRole


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
async def test_get_me__active_user__returns_user_read_with_role(session: AsyncSession) -> None:
    user = User(
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        status="active",
    )
    session.add(user)
    await session.flush()

    role = UserRole(user_id=user.id, role="data_engineer")
    session.add(role)
    await session.commit()

    principal = RequestPrincipal(user_id=user.id, role="data_engineer")
    result = await get_me(session, principal)

    assert result.id == user.id
    assert result.email == "ada@example.com"
    assert result.first_name == "Ada"
    assert result.last_name == "Lovelace"
    assert result.status == "active"
    assert result.role == "data_engineer"


@pytest.mark.asyncio
async def test_get_me__deactivated_user__raises_account_inactive(session: AsyncSession) -> None:
    user = User(
        email="disabled@example.com",
        status="deactivated",
    )
    session.add(user)
    await session.flush()
    role = UserRole(user_id=user.id, role="viewer")
    session.add(role)
    await session.commit()

    principal = RequestPrincipal(user_id=user.id, role="viewer")
    with pytest.raises(AppError) as exc_info:
        await get_me(session, principal)

    assert exc_info.value.code == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_get_me__missing_user__raises_account_inactive(session: AsyncSession) -> None:
    principal = RequestPrincipal(user_id=uuid4(), role="viewer")
    with pytest.raises(AppError) as exc_info:
        await get_me(session, principal)

    assert exc_info.value.code == "ACCOUNT_INACTIVE"
