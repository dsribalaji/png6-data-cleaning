"""Service-level unit tests for get_quarantine feature."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.get_quarantine.service import (
    get_quarantine_service,
)
from planner.modules.datasets.models import Dataset, QuarantineRecord


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
    return RequestPrincipal(user_id=uuid7(), role="data_engineer")


async def _seed(
    session: AsyncSession, count: int, other_count: int = 0
) -> tuple[Dataset, Dataset]:
    """Seed a dataset with `count` quarantine rows and a second dataset with `other_count`."""
    now = datetime.now(UTC)

    dataset = Dataset(
        id=uuid7(),
        name="invoices.csv",
        source="upload",
        file_name="invoices.csv",
        status="profiling",
        version=1,
    )
    other = Dataset(
        id=uuid7(),
        name="orders.csv",
        source="upload",
        file_name="orders.csv",
        status="profiling",
        version=1,
    )
    session.add_all([dataset, other])

    for i in range(count):
        session.add(
            QuarantineRecord(
                id=uuid7(),
                dataset_id=dataset.id,
                row_ref=f"row:{i + 2}",
                reason="Null byte in field",
                created_at=now + timedelta(seconds=i),
            )
        )
    for i in range(other_count):
        session.add(
            QuarantineRecord(
                id=uuid7(),
                dataset_id=other.id,
                row_ref=f"row:{i + 2}",
                reason="Unescaped delimiter",
                created_at=now + timedelta(seconds=i),
            )
        )

    await session.commit()
    return dataset, other


@pytest.mark.asyncio
async def test_get_quarantine__no_records__returns_empty_page(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    dataset, _ = await _seed(async_session, count=0)

    page = await get_quarantine_service(
        dataset_id=dataset.id,
        page=1,
        page_size=20,
        session=async_session,
        principal=principal,
    )

    assert page.items == []
    assert page.total == 0
    assert page.page == 1
    assert page.page_size == 20


@pytest.mark.asyncio
async def test_get_quarantine__records__returns_ordered_camelCase_page(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    dataset, _ = await _seed(async_session, count=3)

    page = await get_quarantine_service(
        dataset_id=dataset.id,
        page=1,
        page_size=20,
        session=async_session,
        principal=principal,
    )

    assert page.total == 3
    assert len(page.items) == 3
    assert [item.row_ref for item in page.items] == ["row:2", "row:3", "row:4"]
    assert all(item.dataset_id == dataset.id for item in page.items)
    assert all(item.reason == "Null byte in field" for item in page.items)

    dumped = page.model_dump(by_alias=True)
    assert dumped["pageSize"] == 20
    assert "datasetId" in dumped["items"][0]
    assert "rowRef" in dumped["items"][0]


@pytest.mark.asyncio
async def test_get_quarantine__multiple_pages__paginates_with_stable_total(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    dataset, _ = await _seed(async_session, count=5)

    page1 = await get_quarantine_service(
        dataset_id=dataset.id,
        page=1,
        page_size=2,
        session=async_session,
        principal=principal,
    )
    page2 = await get_quarantine_service(
        dataset_id=dataset.id,
        page=2,
        page_size=2,
        session=async_session,
        principal=principal,
    )
    page3 = await get_quarantine_service(
        dataset_id=dataset.id,
        page=3,
        page_size=2,
        session=async_session,
        principal=principal,
    )

    assert [len(p.items) for p in (page1, page2, page3)] == [2, 2, 1]
    assert {p.total for p in (page1, page2, page3)} == {5}
    assert [item.row_ref for item in page1.items] == ["row:2", "row:3"]
    assert [item.row_ref for item in page2.items] == ["row:4", "row:5"]
    assert [item.row_ref for item in page3.items] == ["row:6"]


@pytest.mark.asyncio
async def test_get_quarantine__other_dataset_records__excluded(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    """Records are scoped to the requested dataset only."""
    dataset, _ = await _seed(async_session, count=2, other_count=4)

    page = await get_quarantine_service(
        dataset_id=dataset.id,
        page=1,
        page_size=20,
        session=async_session,
        principal=principal,
    )

    assert page.total == 2
    assert all(item.dataset_id == dataset.id for item in page.items)


@pytest.mark.asyncio
async def test_get_quarantine__unknown_dataset__raises_not_found(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    """Unknown dataset id raises 404 NOT_FOUND rather than returning an empty page."""
    with pytest.raises(AppError) as exc_info:
        await get_quarantine_service(
            dataset_id=uuid7(),
            page=1,
            page_size=20,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404