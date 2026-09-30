"""Service for retrieving plan validation results."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.validation.errors import ValidationErrors
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow
from planner.modules.validation.schemas import (
    ReconciliationOut,
    TestCaseOut,
    TestRunOut,
    ValidationResponse,
)


async def get_validation(session: AsyncSession, plan_id: UUID) -> ValidationResponse:
    """Retrieve validation status, test runs, and reconciliations for the current plan version."""
    from planner.modules.execution.public import get_current_version_no

    current = await get_current_version_no(session, plan_id)
    if current <= 0:
        raise ValidationErrors.VALIDATION_NOT_FOUND

    # Load test cases for this plan
    tc_stmt = (
        select(TestCaseRow)
        .where(TestCaseRow.plan_id == plan_id)
        .order_by(TestCaseRow.created_at.asc())
    )
    cases = list((await session.execute(tc_stmt)).scalars().all())

    case_outs: list[TestCaseOut] = []
    all_after_passed = len(cases) > 0

    for c in cases:
        # Load runs for this case and current version, ordered by run_at desc
        tr_stmt = (
            select(TestRunRow)
            .where(
                TestRunRow.test_case_id == c.id,
                TestRunRow.version_no == current,
            )
            .order_by(TestRunRow.run_at.desc(), TestRunRow.id.desc())
        )
        runs = list((await session.execute(tr_stmt)).scalars().all())

        # latestRun: prefer latest after-phase if exists, else latest before-phase
        after_run = next((r for r in runs if r.phase == "after"), None)
        chosen_run = after_run if after_run is not None else (runs[0] if runs else None)

        if after_run is None or after_run.result != "passed":
            all_after_passed = False

        latest_run_out = (
            TestRunOut(
                phase=chosen_run.phase,
                result=chosen_run.result,
                detail=chosen_run.detail,
                run_at=chosen_run.run_at,
            )
            if chosen_run is not None
            else None
        )

        case_outs.append(
            TestCaseOut(
                id=c.id,
                name=c.name,
                type=c.type,
                target_step_id=c.target_step_id,
                latest_run=latest_run_out,
            )
        )

    # Load reconciliations for current version
    rec_stmt = (
        select(ReconciliationRow)
        .where(
            ReconciliationRow.plan_id == plan_id,
            ReconciliationRow.version_no == current,
        )
        .order_by(ReconciliationRow.created_at.asc())
    )
    reconciliations = list((await session.execute(rec_stmt)).scalars().all())
    rec_outs = [
        ReconciliationOut(
            check_name=r.check_name,
            source_value=r.source_value,
            output_value=r.output_value,
            ok=r.ok,
        )
        for r in reconciliations
    ]

    passed = len(cases) > 0 and all_after_passed

    return ValidationResponse(
        plan_id=plan_id,
        version_no=current,
        passed=passed,
        test_cases=case_outs,
        reconciliation=rec_outs,
    )
