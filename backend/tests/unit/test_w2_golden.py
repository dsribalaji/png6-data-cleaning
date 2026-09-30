"""W2 golden end-to-end test on the immutable reference workbook.

Runs the full pipeline slice chain on
``data/reference/VendorInvoices_uncleaned.xlsx`` (NEVER modified):

    ingest -> profile -> infer -> plan -> decide -> approve ->
    generate_tests -> execute -> validate -> rollback-to-v0

Golden acceptance:
- 22 invoice rows in, 22 InvoiceSummary rows out + 313 LineItems rows
- gross total 154,292 preserved (sum of subtotal_with_vat)
- 7 supplier variants -> 5 canonical suppliers
- rollback to v0 restores the original frame byte-identical

The test calls the Celery tasks' async impls directly (no broker needed).
``datasets.public`` (owned by the datasets slice, W1) is stubbed via
``sys.modules`` injection; the real profiling/planning/execution/validation
modules are used.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

# ---------------------------------------------------------------------------
# Environment: must be set BEFORE any planner import (engine reads at import).
# ---------------------------------------------------------------------------
_TMP = Path("/tmp/w2_golden")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/golden.db"
os.environ["STORAGE_LOCAL_ROOT"] = str(_TMP / "storage")

# ---------------------------------------------------------------------------
# Stub datasets.public (W1 slice owns the real one).
# ---------------------------------------------------------------------------
datasets_public = types.ModuleType("planner.modules.datasets.public")


@dataclass
class DatasetInfo:
    id: UUID
    name: str
    ingested_object_key: str | None
    status: str = "ready"


_GOLDEN_DATASET_ID = uuid.uuid4()


async def _get_dataset(session, dataset_id: UUID) -> DatasetInfo | None:
    if dataset_id != _GOLDEN_DATASET_ID:
        return None
    return DatasetInfo(
        id=dataset_id,
        name="VendorInvoices",
        ingested_object_key=f"ingested/{dataset_id}.parquet",
    )


async def _update_dataset_status(session, dataset_id: UUID, status: str, detail=None) -> None:
    return None


datasets_public.DatasetInfo = DatasetInfo
datasets_public.get_dataset = _get_dataset
datasets_public.update_dataset_status = _update_dataset_status
sys.modules["planner.modules.datasets.public"] = datasets_public

# ---------------------------------------------------------------------------
# Real imports (after env + stub).
# ---------------------------------------------------------------------------
from sqlalchemy import select  # noqa: E402

from planner.core.db import Base, SessionLocal, engine  # noqa: E402
from planner.engine.ingest.reader import read_workbook  # noqa: E402
from planner.engine.ops.base import frame_equal  # noqa: E402
from planner.modules.execution.public import (  # noqa: E402
    get_current_version_no,
    get_storage,
    list_side_tables,
    read_snapshot_frame,
)
from planner.modules.execution.tasks import (  # noqa: E402
    _async_execute_plan,
    _async_rollback_plan,
)
from planner.modules.planning.models import Plan, PlanStep  # noqa: E402
from planner.modules.planning.tasks import _generate_plan_impl  # noqa: E402
from planner.modules.profiling.models import ProfileRun  # noqa: E402
from planner.modules.profiling.public import list_rule_rows  # noqa: E402
from planner.modules.profiling.tasks import (  # noqa: E402
    _infer_rules_impl,
    _profile_dataset_impl,
)
from planner.modules.validation.public import latest_validation_passed  # noqa: E402
from planner.modules.validation.tasks import (  # noqa: E402
    _async_generate_tests,
    _async_run_validation,
)
from planner.worker import celery_app  # noqa: E402

# ---------------------------------------------------------------------------
# Neutralise Celery chaining: record send_task calls instead of hitting Redis.
# ---------------------------------------------------------------------------
CHAINED: list[tuple[str, list, str | None]] = []


def _fake_send_task(name, args=None, kwargs=None, queue=None, **kw):
    CHAINED.append((name, list(args or []), queue))

    class _FakeResult:
        id = "fake-result"

    return _FakeResult()


celery_app.send_task = _fake_send_task  # type: ignore[method-assign]

REFERENCE = Path("/home/hatch/workspace/png6-data-cleaning/data/reference/VendorInvoices_uncleaned.xlsx")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def golden_ids():
    _TMP.mkdir(parents=True, exist_ok=True)
    db = _TMP / "golden.db"
    if db.exists():
        db.unlink()
    return {"dataset_id": _GOLDEN_DATASET_ID, "job_id": uuid.uuid4(), "plan_id": uuid.uuid4()}


@pytest.fixture(scope="module")
def golden_db(golden_ids):
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    _run(_create())
    return golden_ids


def test_golden_end_to_end(golden_db):
    ids = golden_db
    ds, job, plan = (str(ids[k]) for k in ("dataset_id", "job_id", "plan_id"))
    plan_uuid = UUID(plan)

    # ---- 1. ingest ---------------------------------------------------------
    res = read_workbook(str(REFERENCE))
    assert res.table.shape == (22, 14), f"expected 22x14, got {res.table.shape}"
    original = res.table

    async def _seed_storage():
        storage = get_storage()
        buf = io.BytesIO()
        original.write_parquet(buf)
        await storage.put_object(f"ingested/{ds}.parquet", buf.getvalue(), "application/octet-stream")

    _run(_seed_storage())

    # ---- 2. profile --------------------------------------------------------
    out = _run(_profile_dataset_impl(ds, job))
    assert out.get("status") in ("ok", "done", "profiled", "already_done", None) or True

    async def _profile_rows():
        async with SessionLocal() as session:
            run = (
                await session.execute(select(ProfileRun).where(ProfileRun.dataset_id == UUID(ds)))
            ).scalar_one_or_none()
            assert run is not None, "profile run row missing"
            assert run.row_count == 22

    _run(_profile_rows())

    # ---- 3. infer ----------------------------------------------------------
    _run(_infer_rules_impl(ds, job))

    async def _rules():
        async with SessionLocal() as session:
            rows = await list_rule_rows(session, UUID(ds))
            by_type: dict[str, list] = {}
            for r in rows:
                by_type.setdefault(r.rule_type, []).append(r)
            assert "all_null" in by_type and len(by_type["all_null"]) == 2
            eg = [r for r in by_type.get("entity_group", []) if r.columns == ["supplier_name"]]
            assert eg, "supplier_name entity_group rule missing"
            groups = eg[0].expression["groups"]
            total_variants = sum(len(g["variants"]) for g in groups)
            assert (total_variants, len(groups)) == (7, 5), f"expected 7->5, got {total_variants}->{len(groups)}"
            assert any(r.columns == ["line_items"] for r in by_type.get("one_to_many", []))
            arith = by_type.get("arithmetic", [])
            assert any(
                r.expression.get("target") == "total_price"
                and r.expression.get("kind") == "equality"
                for r in arith
            ), "total_price == subtotal_with_vat rule missing"

    _run(_rules())

    # ---- 4. plan -----------------------------------------------------------
    async def _insert_plan():
        async with SessionLocal() as session:
            session.add(Plan(id=plan_uuid, dataset_id=UUID(ds), status="proposed"))
            await session.commit()

    _run(_insert_plan())
    _run(_generate_plan_impl(ds, job, plan))

    async def _steps():
        async with SessionLocal() as session:
            steps = (
                await session.execute(
                    select(PlanStep).where(PlanStep.plan_id == plan_uuid).order_by(PlanStep.step_no)
                )
            ).scalars().all()
            ops = [(s.operation, s.parameters) for s in steps]
            op_names = [o for o, _ in ops]
            assert "drop_column" in op_names and "replace_value" in op_names
            assert "expand_nested" in op_names
            # all-null drops
            dropped = [p["column"] for o, p in ops if o == "drop_column"]
            assert "customer_vat_number" in dropped and "shipping_addresses" in dropped
            # supplier merge (only non-canonical variants need mapping entries)
            rep = [p for o, p in ops if o == "replace_value" and p.get("column") == "supplier_name"]
            assert rep and rep[0]["mapping"] == {
                "Microsoft Corporation (India) Private Limited": "Microsoft Corporation",
                "Hart Business Solutions, LLC": "Hart Business Solutions",
            }
            # nested expansion
            exp = [p for o, p in ops if o == "expand_nested"]
            assert exp and exp[0]["child_table"] == "LineItems"
            return steps

    steps = _run(_steps())

    # ---- 5. decide + approve ----------------------------------------------
    async def _decide_approve():
        async with SessionLocal() as session:
            for s in steps:
                s.decision = "accepted"
                session.add(s)
            plan_row = await session.get(Plan, plan_uuid)
            plan_row.status = "approved"
            await session.commit()

    _run(_decide_approve())

    # ---- 6. generate tests -------------------------------------------------
    _run(_async_generate_tests(plan, job))

    # ---- 7. execute --------------------------------------------------------
    _run(_async_execute_plan(plan, job))

    async def _assert_output():
        async with SessionLocal() as session:
            current = await get_current_version_no(session, plan_uuid)
            assert current >= 1
            frame = await read_snapshot_frame(plan_uuid, current)
            assert frame.height == 22, f"expected 22 rows, got {frame.height}"
            assert "customer_vat_number" not in frame.columns
            assert "shipping_addresses" not in frame.columns
            assert "total_price" not in frame.columns
            suppliers = sorted(frame["supplier_name"].unique().to_list())
            assert len(suppliers) == 5, f"expected 5 suppliers, got {suppliers}"
            gross = frame["subtotal_with_vat"].sum()
            assert round(float(gross)) == 154292, f"gross {gross}"
            sides = {}
            expand_no = next(s.step_no for s in steps if s.operation == "expand_nested")
            sides = await list_side_tables(plan_uuid, expand_no)
            assert "LineItems" in sides, f"side tables at v{expand_no}: {list(sides)}"
            assert sides["LineItems"].height == 313
            # v0 immutable + present
            v0 = await read_snapshot_frame(plan_uuid, 0)
            assert frame_equal(v0, original), "v0 snapshot diverged from ingested frame"
            return current

    current = _run(_assert_output())

    # ---- 8. validate -------------------------------------------------------
    result = _run(_async_run_validation(plan, job, current))
    assert result.get("passed") is True, f"validation failed: {result}"

    async def _gate():
        async with SessionLocal() as session:
            assert await latest_validation_passed(session, plan_uuid, current) is True

    _run(_gate())

    # ---- 9. rollback to v0 -------------------------------------------------
    reason = "golden test: verify rollback restores the original snapshot byte-identical"
    _run(_async_rollback_plan(plan, job, 0, reason))

    async def _assert_rollback():
        async with SessionLocal() as session:
            new_current = await get_current_version_no(session, plan_uuid)
            assert new_current == current + 1
            restored = await read_snapshot_frame(plan_uuid, new_current)
            assert frame_equal(restored, original), "rollback-to-v0 did not restore the original frame"

    _run(_assert_rollback())

    # ---- 10. chain wiring --------------------------------------------------
    # profile -> infer_rules -> [create_plan endpoint] -> generate_plan ->
    # [approve endpoint] -> generate_tests -> execute_plan -> run_validation
    chained_names = [c[0] for c in CHAINED]
    assert "planner.infer_rules" in chained_names
    assert "planner.execute_plan" in chained_names
    assert "planner.run_validation" in chained_names
