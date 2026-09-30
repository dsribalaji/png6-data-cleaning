"""Public interface for the planning module (Backend.md).

Modules import each other ONLY via public.py.
Mount: app.include_router(r, prefix='/api/v1') for r in routers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.planning.features.approve_plan.router import router as approve_plan_router
from planner.modules.planning.features.create_plan.router import router as create_plan_router
from planner.modules.planning.features.decide_step.router import router as decide_step_router
from planner.modules.planning.features.get_plan.router import router as get_plan_router
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep

routers: list[APIRouter] = [
    create_plan_router,
    get_plan_router,
    decide_step_router,
    approve_plan_router,
]


async def get_plan_row(session: AsyncSession, plan_id: UUID) -> Plan | None:
    """Retrieve the Plan database record."""
    stmt = select(Plan).where(Plan.id == plan_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_decided_steps(
    session: AsyncSession, plan_id: UUID
) -> list[dict[str, Any]]:
    """Retrieve all accepted or edited steps for execution, ordered by step_no."""
    stmt = (
        select(PlanStep)
        .where(
            PlanStep.plan_id == plan_id,
            PlanStep.decision.in_(["accepted", "edited"]),
        )
        .order_by(PlanStep.step_no.asc())
    )
    res = await session.execute(stmt)
    steps = res.scalars().all()
    return [
        {
            "id": s.id,
            "step_no": s.step_no,
            "operation": s.operation,
            "parameters": s.parameters,
        }
        for s in steps
    ]


async def get_plan_steps_with_loss(
    session: AsyncSession, plan_id: UUID
) -> list[tuple[PlanStep, LossEstimateRow | None]]:
    """Retrieve all plan steps along with their loss estimates, ordered by step_no."""
    stmt = (
        select(PlanStep, LossEstimateRow)
        .outerjoin(LossEstimateRow, LossEstimateRow.step_id == PlanStep.id)
        .where(PlanStep.plan_id == plan_id)
        .order_by(PlanStep.step_no.asc())
    )
    res = await session.execute(stmt)
    return list(res.all())
