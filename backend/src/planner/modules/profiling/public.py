"""Public interface for the profiling module (Backend.md).

Modules import each other ONLY via public.py.
Mount: app.include_router(r, prefix='/api/v1') for r in routers.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.profiling.features.get_profile.router import router as get_profile_router
from planner.modules.profiling.features.get_rules.router import router as get_rules_router
from planner.modules.profiling.models import (
    ColumnProfileRow,
    InferredRuleRow,
    ProfileRun,
    ProfileRunRow,
)

routers: list[APIRouter] = [get_profile_router, get_rules_router]


async def get_profile_run(session: AsyncSession, dataset_id: UUID) -> ProfileRunRow | None:
    """Retrieve the profile run record for a dataset."""
    stmt = select(ProfileRun).where(ProfileRun.dataset_id == dataset_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_rule_rows(session: AsyncSession, dataset_id: UUID) -> list[InferredRuleRow]:
    """Retrieve all inferred rule records for a dataset, ordered by confidence desc."""
    stmt = (
        select(InferredRuleRow)
        .where(InferredRuleRow.dataset_id == dataset_id)
        .order_by(InferredRuleRow.confidence.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_column_profile_rows(
    session: AsyncSession, dataset_id: UUID
) -> list[ColumnProfileRow]:
    """Retrieve all column profile records for a dataset, ordered by ordinal asc."""
    stmt = (
        select(ColumnProfileRow)
        .where(ColumnProfileRow.dataset_id == dataset_id)
        .order_by(ColumnProfileRow.ordinal.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
