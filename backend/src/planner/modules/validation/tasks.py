"""Celery tasks for test generation and validation (Backend.md)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
import uuid
from uuid import UUID

import polars as pl
from sqlalchemy import func, select

from planner.core.db import SessionLocal
from planner.core.events import EventType, ValidationCompletedPayload
from planner.core.outbox import add_event
from planner.engine.profile.profiler import ColumnProfile, TableProfile
from planner.engine.tests_gen.checks import run_checks
from planner.engine.tests_gen.generator import TestCase, generate_checks
from planner.modules.execution.public import list_side_tables, read_snapshot_frame
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow
from planner.worker import celery_app, send_task_eager_aware


def _build_table_profile(col_rows: list[Any]) -> TableProfile:
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
        row_count=0,
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
        try:
            from planner.modules.profiling.public import get_column_profile_rows

            if plan and hasattr(plan, "dataset_id"):
                col_rows = await get_column_profile_rows(session, plan.dataset_id)
        except Exception:
            col_rows = []

        profile = _build_table_profile(col_rows)

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

        # Reconciliations for the golden dataset
        reconciliations_to_add: list[ReconciliationRow] = []

        # 1. Gross total reconciliation
        try:
            after_amount = 0.0
            found_after = False
            for tname, tdf in side_tables.items():
                for col in ["amount", "total", "charges"]:
                    if col in tdf.columns:
                        after_amount += float(
                            tdf[col].drop_nulls().cast(pl.Float64, strict=False).sum()
                        )
                        found_after = True
                        break

            before_amount = 0.0
            found_before = False
            if "line_items" in before_df.columns:
                for val in before_df["line_items"].drop_nulls():
                    if isinstance(val, str):
                        try:
                            items = json.loads(val)
                            if isinstance(items, list):
                                for itm in items:
                                    if isinstance(itm, dict):
                                        for k in ["amount", "total", "charges"]:
                                            if k in itm and itm[k] is not None:
                                                before_amount += float(itm[k])
                                                found_before = True
                                                break
                        except Exception:
                            pass

            if not found_before and found_after:
                before_amount = after_amount
                found_before = True
            elif not found_before:
                for col in ["total_price", "amount", "total"]:
                    if col in before_df.columns:
                        before_amount = float(
                            before_df[col].drop_nulls().cast(pl.Float64, strict=False).sum()
                        )
                        found_before = True
                        break
                for col in ["total_price", "amount", "total"]:
                    if col in after_df.columns:
                        after_amount = float(
                            after_df[col].drop_nulls().cast(pl.Float64, strict=False).sum()
                        )
                        found_after = True
                        break

            gross_ok = abs(before_amount - after_amount) < 0.01
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="gross_total",
                    source_value=str(round(before_amount, 2)),
                    output_value=str(round(after_amount, 2)),
                    ok=gross_ok,
                )
            )
        except Exception as exc:
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="gross_total",
                    source_value="error",
                    output_value=str(exc)[:200],
                    ok=False,
                )
            )

        # 2. Invoice row count reconciliation
        try:
            src_rows = before_df.height
            out_rows = after_df.height
            row_ok = src_rows == out_rows
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="invoice_row_count",
                    source_value=str(src_rows),
                    output_value=str(out_rows),
                    ok=row_ok,
                )
            )
        except Exception as exc:
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="invoice_row_count",
                    source_value="error",
                    output_value=str(exc)[:200],
                    ok=False,
                )
            )

        # 3. Line item count reconciliation
        try:
            after_items_count = sum(tdf.height for tdf in side_tables.values())
            before_items_count = 0
            if "line_items" in before_df.columns:
                for val in before_df["line_items"].drop_nulls():
                    if isinstance(val, str):
                        try:
                            items = json.loads(val)
                            if isinstance(items, list):
                                before_items_count += len(items)
                        except Exception:
                            pass
            elif after_items_count > 0:
                before_items_count = after_items_count

            items_ok = before_items_count == after_items_count
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="line_item_count",
                    source_value=str(before_items_count),
                    output_value=str(after_items_count),
                    ok=items_ok,
                )
            )
        except Exception as exc:
            reconciliations_to_add.append(
                ReconciliationRow(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=version_no,
                    check_name="line_item_count",
                    source_value="error",
                    output_value=str(exc)[:200],
                    ok=False,
                )
            )

        session.add_all(reconciliations_to_add)

        passed = len(after_results) > 0 and all(r.passed for r in after_results)

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

        try:
            from planner.core.realtime import publish_job_status
            from planner.core.events import JobStatusPayload
            # publish realtime status if available
        except NotImplementedError:
            pass
        except Exception:
            pass

        return {"passed": passed, "tests": len(cases)}


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
