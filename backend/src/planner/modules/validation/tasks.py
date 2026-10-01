"""Celery tasks for test generation and validation (Backend.md)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from planner.core.audit import record_audit
from planner.core.db import SessionLocal
from planner.core.events import EventType, ValidationCompletedPayload
from planner.core.outbox import add_event
from planner.engine.profile.profiler import ColumnProfile, TableProfile
from planner.engine.tests_gen.checks import run_checks
from planner.engine.tests_gen.generator import TestCase, generate_checks
from planner.engine.tests_gen.reconcile import reconcile
from planner.modules.execution.public import list_side_tables, read_snapshot_frame
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow
from planner.worker import celery_app, send_task_eager_aware

logger = logging.getLogger(__name__)


def _build_table_profile(col_rows: list[Any], row_count: int = 0) -> TableProfile:
    """Construct a TableProfile from profiling column rows or dictionaries."""
    columns: list[ColumnProfile] = []
    for idx, r in enumerate(col_rows):
        if isinstance(r, ColumnProfile):
            columns.append(r)
        elif isinstance(r, dict):
            columns.append(
                ColumnProfile(
                    name=r.get("name", f"col_{idx}"),
                    ordinal=r.get("ordinal", idx),
                    physical_type=r.get("physical_type", "String"),
                    semantic_type=r.get("semantic_type", "unknown"),
                    null_count=r.get("null_count", 0),
                    null_pct=float(r.get("null_pct", 0.0)),
                    distinct_count=r.get("distinct_count", 0),
                    min_value=r.get("min_value"),
                    max_value=r.get("max_value"),
                    mean_value=r.get("mean_value"),
                    flags=r.get("flags", []),
                )
            )
        else:
            columns.append(
                ColumnProfile(
                    name=getattr(r, "name", getattr(r, "column_name", f"col_{idx}")),
                    ordinal=getattr(r, "ordinal", idx),
                    physical_type=getattr(r, "physical_type", "String"),
                    semantic_type=getattr(r, "semantic_type", "unknown"),
                    null_count=getattr(r, "null_count", 0),
                    null_pct=float(getattr(r, "null_pct", 0.0)),
                    distinct_count=getattr(r, "distinct_count", 0),
                    min_value=getattr(r, "min_value", None),
                    max_value=getattr(r, "max_value", None),
                    mean_value=getattr(r, "mean_value", None),
                    flags=getattr(r, "flags", []),
                )
            )

    return TableProfile(
        table_name="dataset",
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        issues=[],
    )


async def _async_generate_tests(plan_id: str, job_id: str) -> dict[str, Any]:
    plan_uuid = UUID(plan_id)

    async with SessionLocal() as session:
        # Idempotency check: if TestCaseRow rows exist for plan, skip to chaining
        count_stmt = select(func.count(TestCaseRow.id)).where(TestCaseRow.plan_id == plan_uuid)
        existing_count = (await session.execute(count_stmt)).scalar() or 0
        if existing_count > 0:
            send_task_eager_aware(
                "planner.execute_plan",
                args=[plan_id, job_id],
                queue="execute",
            )
            return {"tests": existing_count, "status": "already_generated"}

        # Lazy import planning.public
        try:
            from planner.modules.planning.public import get_decided_steps, get_plan_row
        except (ImportError, AttributeError) as exc:
            raise RuntimeError("planning.public not implemented") from exc

        plan = await get_plan_row(session, plan_uuid)
        steps = await get_decided_steps(session, plan_uuid)

        # Lazy import profiling.public (defensive)
        col_rows = []
        row_count = 0
        try:
            from planner.modules.profiling.public import get_column_profile_rows, get_profile_run

            if plan and hasattr(plan, "dataset_id"):
                col_rows = await get_column_profile_rows(session, plan.dataset_id)
                run = await get_profile_run(session, plan.dataset_id)
                row_count = int(getattr(run, "row_count", 0) or 0)
        except Exception as exc:  # noqa: BLE001 -- profiling data is optional for validation
            logger.debug("Profiling data unavailable for validation: %s", exc)
            col_rows = []

        profile = _build_table_profile(col_rows, row_count)

        plan_steps_dicts = [
            {
                "step_no": s["step_no"],
                "op": s.get("operation") or s.get("op", ""),
                "params": s.get("parameters") or s.get("params", {}),
            }
            for s in steps
        ]

        generated = generate_checks(plan_steps_dicts, profile)

        for case in generated:
            tc_row = TestCaseRow(
                id=uuid.uuid4(),
                plan_id=plan_uuid,
                type=case.type,
                target_step_id=None,
                name=case.name,
                definition=case.definition,
            )
            session.add(tc_row)

        await session.commit()

        send_task_eager_aware(
            "planner.execute_plan",
            args=[plan_id, job_id],
            queue="execute",
        )
        return {"tests": len(generated)}


@celery_app.task(
    name="planner.generate_tests",
    queue="validate",
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def generate_tests(plan_id: str, job_id: str) -> dict[str, Any]:
    """Generate deterministic test cases from plan steps and dataset profile."""
    return asyncio.run(_async_generate_tests(plan_id, job_id))


async def _async_run_validation(
    plan_id: str, job_id: str, version_no: int
) -> dict[str, Any]:
    plan_uuid = UUID(plan_id)

    async with SessionLocal() as session:
        # Load test cases for plan
        tc_stmt = (
            select(TestCaseRow)
            .where(TestCaseRow.plan_id == plan_uuid)
            .order_by(TestCaseRow.created_at.asc())
        )
        test_case_rows = list((await session.execute(tc_stmt)).scalars().all())
        if not test_case_rows:
            return {"status": "no_tests", "plan_id": plan_id}

        before_df = await read_snapshot_frame(plan_uuid, 0)
        after_df = await read_snapshot_frame(plan_uuid, version_no)
        side_tables = await list_side_tables(plan_uuid, version_no)

        cases = [
            TestCase(
                name=row.name,
                type=row.type,
                target=None,
                definition=row.definition,
            )
            for row in test_case_rows
        ]

        before_results = run_checks(cases, before_df, {"main": before_df})
        after_results = run_checks(cases, after_df, {"main": after_df, **side_tables})

        case_id_by_name = {row.name: row.id for row in test_case_rows}

        for res in before_results:
            cid = case_id_by_name.get(res.name)
            if cid:
                session.add(
                    TestRunRow(
                        id=uuid.uuid4(),
                        test_case_id=cid,
                        version_no=version_no,
                        phase="before",
                        result="passed" if res.passed else "failed",
                        detail=res.detail,
                    )
                )

        for res in after_results:
            cid = case_id_by_name.get(res.name)
            if cid:
                session.add(
                    TestRunRow(
                        id=uuid.uuid4(),
                        test_case_id=cid,
                        version_no=version_no,
                        phase="after",
                        result="passed" if res.passed else "failed",
                        detail=res.detail,
                    )
                )

        # Reconciliation (FR-042): recomputed from the source frame, dataset-agnostic.
        from planner.modules.planning.public import get_decided_steps

        steps = await get_decided_steps(session, plan_uuid)
        recs = reconcile(before_df, after_df, side_tables, steps)
        session.add_all(
            ReconciliationRow(
                id=uuid.uuid4(),
                plan_id=plan_uuid,
                version_no=version_no,
                check_name=r.check_name,
                source_value=f"{r.source_value:.2f}" if r.source_value % 1 else f"{r.source_value:.0f}",
                output_value=f"{r.output_value:.2f}" if r.output_value % 1 else f"{r.output_value:.0f}",
                ok=r.ok,
            )
            for r in recs
        )

        # FR-043: export gate needs every test AND every reconciliation to pass.
        passed = (
            len(after_results) > 0
            and all(r.passed for r in after_results)
            and all(r.ok for r in recs)
        )

        await add_event(
            session,
            EventType.VALIDATION_COMPLETED.value,
            ValidationCompletedPayload(
                plan_id=plan_uuid,
                version_no=version_no,
                passed=passed,
            ),
        )

        await session.commit()
        await record_audit(
            session=session,
            event_type="validation.completed",
            object_type="plan",
            object_id=plan_id,
            details={"versionNo": version_no, "passed": passed, "tests": len(cases),
                     "reconciliationsOk": sum(r.ok for r in recs), "reconciliations": len(recs)},
        )

        # publish realtime status if available (not wired yet)

        return {"passed": passed, "tests": len(cases), "reconciliations": len(recs)}


@celery_app.task(
    name="planner.run_validation",
    queue="validate",
    soft_time_limit=300,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def run_validation(plan_id: str, job_id: str, version_no: int) -> dict[str, Any]:
    """Execute before/after tests and reconciliations against snapshot frames."""
    return asyncio.run(_async_run_validation(plan_id, job_id, version_no))
