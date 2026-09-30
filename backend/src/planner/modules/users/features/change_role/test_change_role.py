"""Unit tests for the change_role feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.users.features.change_role.schemas import ChangeRoleRequest
from planner.modules.users.features.change_role.service import change_role_service
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


async def _make_user(session: AsyncSession, email: str, role: str) -> User:
    user = User(email=email, status="active")
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role=role))
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_change_role__existing_user__replaces_role_row(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "engineer@example.com", "data_engineer")

    result = await change_role_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
        ChangeRoleRequest(role="auditor"),
    )

    assert result.id == target.id
    assert result.role == "auditor"
    assert result.email == "engineer@example.com"

    roles = (await session.execute(select(UserRole))).scalars().all()
    target_roles = [r for r in roles if r.user_id == target.id]
    assert len(target_roles) == 1
    assert target_roles[0].role == "auditor"


@pytest.mark.asyncio
async def test_change_role__user_without_role_row__inserts_role(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = User(email="roleless@example.com", status="active")
    session.add(target)
    await session.commit()

    result = await change_role_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
        ChangeRoleRequest(role="viewer"),
    )

    assert result.role == "viewer"
    roles = (await session.execute(select(UserRole))).scalars().all()
    assert [(r.user_id, r.role) for r in roles if r.user_id == target.id] == [(target.id, "viewer")]


@pytest.mark.asyncio
async def test_change_role__own_account__raises_forbidden(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")

    with pytest.raises(AppError) as exc_info:
        await change_role_service(
            session,
            RequestPrincipal(user_id=actor.id, role="administrator"),
            actor.id,
            ChangeRoleRequest(role="viewer"),
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.status == 403

    await session.refresh(actor)
    role_row = (
        await session.execute(select(UserRole).where(UserRole.user_id == actor.id))
    ).scalar_one()
    assert role_row.role == "administrator"


@pytest.mark.asyncio
async def test_change_role__unknown_user__raises_not_found(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    missing_id = uuid4()

    with pytest.raises(AppError) as exc_info:
        await change_role_service(
            session,
            RequestPrincipal(user_id=actor.id, role="administrator"),
            missing_id,
            ChangeRoleRequest(role="viewer"),
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_change_role__deactivated_user__role_still_changeable(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "gone@example.com", "viewer")
    target.status = "deactivated"
    await session.commit()

    result = await change_role_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
        ChangeRoleRequest(role="data_engineer"),
    )

    assert result.role == "data_engineer"
    assert result.status == "deactivated"
