"""Service-level unit tests for list_datasets feature."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.list_datasets.service import list_datasets_service
from planner.modules.datasets.models import Dataset


@pytest.fixture
async def async_session() -> AsyncSession:
    """Provide an in-memory SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def principal() -> RequestPrincipal:
    return RequestPrincipal(user_id=uuid7(), role="viewer")


@pytest.mark.asyncio
async def test_list_datasets__empty_db__returns_empty_page(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    page = await list_datasets_service(
        page=1,
        page_size=20,
        session=async_session,
        principal=principal,
    )

    assert page.items == []
    assert page.total == 0
    assert page.page == 1
    assert page.page_size == 20

    dumped = page.model_dump(by_alias=True)
    assert dumped["pageSize"] == 20
    assert dumped["total"] == 0
    assert dumped["items"] == []


@pytest.mark.asyncio
async def test_list_datasets__multiple_datasets__returns_ordered_paginated(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    now = datetime.now(UTC)
    for i in range(5):
        ds = Dataset(
            id=uuid7(),
            name=f"dataset_{i}.csv",
            source="upload",
            file_name=f"dataset_{i}.csv",
            status="profiled",
            row_count=100 + i,
            column_count=10,
            created_at=now,
        )
        async_session.add(ds)
    await async_session.commit()

    # Request page 1, size 2
    page1 = await list_datasets_service(
        page=1,
        page_size=2,
        session=async_session,
        principal=principal,
    )
    assert len(page1.items) == 2
    assert page1.total == 5
    assert page1.page == 1
    assert page1.page_size == 2

    # Check wire serialization
    dumped = page1.model_dump(by_alias=True)
    assert dumped["pageSize"] == 2
    assert len(dumped["items"]) == 2
    assert "fileName" in dumped["items"][0]
    assert "rowCount" in dumped["items"][0]

    # Request page 2, size 2
    page2 = await list_datasets_service(
        page=2,
        page_size=2,
        session=async_session,
        principal=principal,
    )
    assert len(page2.items) == 2
    assert page2.total == 5
    assert page2.page == 2

    # Request page 3, size 2
    page3 = await list_datasets_service(
        page=3,
        page_size=2,
        session=async_session,
        principal=principal,
    )
    assert len(page3.items) == 1
    assert page3.total == 5
    assert page3.page == 3
