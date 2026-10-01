"""Unit tests for the deactivate_user feature service layer (Backend.md)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal, hash_token
from planner.modules.users.features.deactivate_user.service import deactivate_user_service
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


async def _make_user(session: AsyncSession, email: str, role: str) -> User:
    user = User(email=email, status="active")
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role=role))
    await session.commit()
    return user


def _refresh_token(user_id: UUID, *, revoked: bool = False) -> RefreshToken:
    now = datetime.now(UTC)
    return RefreshToken(
        id=uuid7(),
        user_id=user_id,
        token_hash=hash_token(f"token_{uuid4().hex}"),
        family_id=uuid7(),
        expires_at=now + timedelta(days=7),
        revoked_at=now if revoked else None,
    )


@pytest.mark.asyncio
async def test_deactivate_user__active_user__sets_status_and_returns_user(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "engineer@example.com", "data_engineer")

    result = await deactivate_user_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
    )

    assert result.id == target.id
    assert result.status == "deactivated"
    assert result.role == "data_engineer"

    await session.refresh(target)
    assert target.status == "deactivated"


@pytest.mark.asyncio
async def test_deactivate_user__live_refresh_tokens__all_revoked(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "engineer@example.com", "data_engineer")

    session.add(_refresh_token(target.id))
    session.add(_refresh_token(target.id))
    session.add(_refresh_token(actor.id))
    await session.commit()

    await deactivate_user_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
    )

    target_tokens = (
        await session.execute(select(RefreshToken).where(RefreshToken.user_id == target.id))
    ).scalars().all()
    assert len(target_tokens) == 2
    assert all(t.revoked_at is not None for t in target_tokens)

    actor_tokens = (
        await session.execute(select(RefreshToken).where(RefreshToken.user_id == actor.id))
    ).scalars().all()
    assert all(t.revoked_at is None for t in actor_tokens)


@pytest.mark.asyncio
async def test_deactivate_user__already_revoked_tokens__revoked_at_unchanged(
    session: AsyncSession,
) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "engineer@example.com", "viewer")

    already = _refresh_token(target.id, revoked=True)
    session.add(already)
    await session.commit()

    await deactivate_user_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
    )

    await session.refresh(already)
    assert already.revoked_at is not None


@pytest.mark.asyncio
async def test_deactivate_user__own_account__raises_forbidden(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")

    with pytest.raises(AppError) as exc_info:
        await deactivate_user_service(
            session,
            RequestPrincipal(user_id=actor.id, role="administrator"),
            actor.id,
        )

    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.status == 403

    await session.refresh(actor)
    assert actor.status == "active"


@pytest.mark.asyncio
async def test_deactivate_user__unknown_user__raises_not_found(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")

    with pytest.raises(AppError) as exc_info:
        await deactivate_user_service(
            session,
            RequestPrincipal(user_id=actor.id, role="administrator"),
            uuid4(),
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_deactivate_user__already_deactivated__idempotent(session: AsyncSession) -> None:
    actor = await _make_user(session, "admin@example.com", "administrator")
    target = await _make_user(session, "gone@example.com", "viewer")
    target.status = "deactivated"
    await session.commit()

    result = await deactivate_user_service(
        session,
        RequestPrincipal(user_id=actor.id, role="administrator"),
        target.id,
    )

    assert result.status == "deactivated"
