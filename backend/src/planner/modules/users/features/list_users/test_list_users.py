"""Unit tests for the list_users feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.security import RequestPrincipal
from planner.modules.users.features.list_users.service import list_users_service
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


async def _make_user(
    session: AsyncSession,
    email: str,
    role: str | None = "viewer",
    status: str = "active",
) -> User:
    user = User(email=email, first_name="Test", last_name="User", status=status)
    session.add(user)
    await session.flush()
    if role is not None:
        session.add(UserRole(user_id=user.id, role=role))
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_list_users__multiple_users__returns_page_with_joined_roles(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", role="administrator")
    await _make_user(session, "engineer@example.com", role="data_engineer")
    await _make_user(session, "auditor@example.com", role="auditor")

    page = await list_users_service(
        page=1,
        page_size=20,
        session=session,
        actor=RequestPrincipal(user_id=actor.id, role="administrator"),
    )

    assert page.total == 3
    assert page.page == 1
    assert page.page_size == 20
    assert {item.role for item in page.items} == {
        "administrator",
        "data_engineer",
        "auditor",
    }
    assert all(item.id is not None for item in page.items)


@pytest.mark.asyncio
async def test_list_users__second_page__returns_remainder_and_full_total(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", role="administrator")
    await _make_user(session, "b@example.com", role="viewer")
    await _make_user(session, "c@example.com", role="viewer")

    page = await list_users_service(
        page=2,
        page_size=2,
        session=session,
        actor=RequestPrincipal(user_id=actor.id, role="administrator"),
    )

    assert page.total == 3
    assert len(page.items) == 1


@pytest.mark.asyncio
async def test_list_users__user_without_role_row__returns_null_role(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", role="administrator")
    await _make_user(session, "roleless@example.com", role=None)

    page = await list_users_service(
        page=1,
        page_size=20,
        session=session,
        actor=RequestPrincipal(user_id=actor.id, role="administrator"),
    )

    roleless = [item for item in page.items if item.email == "roleless@example.com"]
    assert len(roleless) == 1
    assert roleless[0].role is None


@pytest.mark.asyncio
async def test_list_users__deactivated_user__included_with_deactivated_status(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", role="administrator")
    await _make_user(session, "gone@example.com", role="viewer", status="deactivated")

    page = await list_users_service(
        page=1,
        page_size=20,
        session=session,
        actor=RequestPrincipal(user_id=actor.id, role="administrator"),
    )

    statuses = {item.email: item.status for item in page.items}
    assert statuses["gone@example.com"] == "deactivated"


@pytest.mark.asyncio
async def test_list_users__no_users__returns_empty_page(session: AsyncSession) -> None:
    page = await list_users_service(
        page=1,
        page_size=20,
        session=session,
        actor=RequestPrincipal(user_id=uuid4(), role="administrator"),
    )

    assert page.total == 0
    assert page.items == []
