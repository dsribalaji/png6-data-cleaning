"""Unit tests for get_profile feature."""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.profiling.features.get_profile.service import get_profile
from planner.modules.profiling.models import ColumnProfileRow, ProfileRun


@pytest.fixture
async def test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={
            "schema_translate_map": {
                "profiling": None,
                "planning": None,
                "execution": None,
                "validation": None,
                "datasets": None,
                "users": None,
                "audit": None,
                "model_config": None,
                "evaluation": None,
            }
        },
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_profile_success(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    run = ProfileRun(
        dataset_id=dataset_id,
        row_count=100,
        column_count=2,
        issues=["all-null-columns"],
    )
    col1 = ColumnProfileRow(
        dataset_id=dataset_id,
        column_name="id",
        ordinal=0,
        physical_type="Int64",
        semantic_type="identifier",
        null_count=0,
        null_pct=0.0,
        distinct_count=100,
        min_value="1",
        max_value="100",
        mean_value=50.5,
        flags=[],
    )
    col2 = ColumnProfileRow(
        dataset_id=dataset_id,
        column_name="vendor",
        ordinal=1,
        physical_type="String",
        semantic_type="category",
        null_count=5,
        null_pct=0.05,
        distinct_count=10,
        min_value="Acme",
        max_value="Zeta",
        mean_value=None,
        flags=["sparse_5"],
    )
    test_session.add_all([run, col1, col2])
    await test_session.commit()

    resp = await get_profile(test_session, dataset_id)
    assert resp.dataset_id == dataset_id
    assert resp.row_count == 100
    assert resp.column_count == 2
    assert len(resp.columns) == 2
    assert resp.columns[0].name == "id"
    assert resp.columns[1].name == "vendor"

    # Assert camelCase serialization
    dumped = resp.model_dump(by_alias=True)
    assert "datasetId" in dumped
    assert "rowCount" in dumped
    assert "columnCount" in dumped
    assert "profiledAt" in dumped
    assert "physicalType" in dumped["columns"][0]
    assert "semanticType" in dumped["columns"][0]
    assert "nullCount" in dumped["columns"][0]
    assert "nullPct" in dumped["columns"][0]


@pytest.mark.asyncio
async def test_get_profile_not_found(test_session: AsyncSession):
    missing_id = uuid.uuid4()
    with pytest.raises(AppError) as exc_info:
        await get_profile(test_session, missing_id)
    assert exc_info.value.code == "PROFILE_NOT_FOUND"
    assert exc_info.value.status == 404
