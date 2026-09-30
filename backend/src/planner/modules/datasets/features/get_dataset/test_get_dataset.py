"""Service-level unit tests for get_dataset feature."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.errors import AppError
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.get_dataset.service import get_dataset_service
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
    return RequestPrincipal(user_id=uuid7(), role="auditor")


@pytest.mark.asyncio
async def test_get_dataset__existing_id__returns_dataset(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    ds_id = uuid7()
    dataset = Dataset(
        id=ds_id,
        name="sales_2026.xlsx",
        source="upload",
        file_name="sales_2026.xlsx",
        status="profiled",
        row_count=500,
        column_count=12,
        raw_object_key=f"raw/{ds_id}/sales_2026.xlsx",
    )
    async_session.add(dataset)
    await async_session.commit()

    result = await get_dataset_service(
        dataset_id=ds_id,
        session=async_session,
        principal=principal,
    )

    assert result.id == ds_id
    assert result.name == "sales_2026.xlsx"
    assert result.file_name == "sales_2026.xlsx"
    assert result.row_count == 500
    assert result.column_count == 12
    assert result.status == "profiled"

    dumped = result.model_dump(by_alias=True)
    assert dumped["fileName"] == "sales_2026.xlsx"
    assert dumped["rowCount"] == 500
    assert dumped["columnCount"] == 12


@pytest.mark.asyncio
async def test_get_dataset__nonexistent_id__raises_not_found(
    async_session: AsyncSession,
    principal: RequestPrincipal,
) -> None:
    missing_id = uuid7()

    with pytest.raises(AppError) as exc_info:
        await get_dataset_service(
            dataset_id=missing_id,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status == 404
