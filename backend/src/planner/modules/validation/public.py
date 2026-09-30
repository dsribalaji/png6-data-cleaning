"""Public API and cross-module interfaces for the validation module (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.validation.features.get_validation.router import (
    router as get_validation_router,
)
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow

# Mount: app.include_router(r, prefix='/api/v1') for r in routers
routers = [get_validation_router]


async def latest_validation_passed(
    session: AsyncSession, plan_id: UUID, version_no: int
) -> bool:
    """Check if all test cases for the plan passed in their latest after-phase run.

    Export gate depends on this check: requires >= 1 test case and every test case's
    latest after-phase run for version_no to have result == 'passed'.
    """
    tc_stmt = select(TestCaseRow).where(TestCaseRow.plan_id == plan_id)
    cases = list((await session.execute(tc_stmt)).scalars().all())
    if not cases:
        return False

    for c in cases:
        tr_stmt = (
            select(TestRunRow)
            .where(
                TestRunRow.test_case_id == c.id,
                TestRunRow.version_no == version_no,
                TestRunRow.phase == "after",
            )
            .order_by(TestRunRow.run_at.desc(), TestRunRow.id.desc())
            .limit(1)
        )
        run = (await session.execute(tr_stmt)).scalars().first()
        if run is None or run.result != "passed":
            return False

    rec_stmt = select(ReconciliationRow.ok).where(
        ReconciliationRow.plan_id == plan_id, ReconciliationRow.version_no == version_no
    )
    recs = list((await session.execute(rec_stmt)).scalars().all())
    return bool(recs) and all(recs)


__all__ = ["latest_validation_passed", "routers"]
