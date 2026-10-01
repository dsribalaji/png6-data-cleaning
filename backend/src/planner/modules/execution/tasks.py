"""Celery tasks for plan execution and rollback (Backend.md)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import select

from planner.core.audit import record_audit
from planner.core.db import SessionLocal
from planner.core.events import (
    EventType,
    JobFailedPayload,
    JobStatusPayload,
    PlanExecutedPayload,
    PlanStepExecutedPayload,
    RollbackCompletedPayload,
)
from planner.core.outbox import add_event
from planner.engine.ingest.parquet import read_parquet
from planner.engine.ops.base import OPS
from planner.modules.execution.models import PipelineVersion, RollbackRow
from planner.modules.execution.public import get_storage, read_snapshot_frame
from planner.worker import celery_app, send_task_eager_aware


async def _async_execute_plan(plan_id: str, job_id: str) -> dict[str, Any]:
    plan_uuid = UUID(plan_id)
    job_uuid = UUID(job_id)

    async with SessionLocal() as session:
        try:
            # Query existing pipeline versions
            stmt = (
                select(PipelineVersion)
                .where(PipelineVersion.plan_id == plan_uuid)
                .order_by(PipelineVersion.version_no.asc())
            )
            res = await session.execute(stmt)
            existing_versions = list(res.scalars().all())
            max_version_no = max((v.version_no for v in existing_versions), default=0)

            # Lazy import planning.public
            try:
                from planner.modules.planning.public import get_decided_steps, get_plan_row
            except (ImportError, AttributeError) as exc:
                raise RuntimeError("planning.public not implemented") from exc

            plan = await get_plan_row(session, plan_uuid)
            if not plan or getattr(plan, "status", None) != "approved":
                raise RuntimeError("PLAN_NOT_APPROVED: Only an approved plan can be executed.")

            steps = await get_decided_steps(session, plan_uuid)

            # Idempotency check: if versions already match decided steps
            # Idempotency check: if versions already match decided steps
            # (v0 is base; versions-1 is count of executed steps)
            if max_version_no > 0 and len(existing_versions) - 1 == len(steps):
                return {"status": "already_done", "plan_id": plan_id}

            storage = get_storage()

            # Load base frame
            v0_version = next((v for v in existing_versions if v.version_no == 0), None)
            if v0_version is None:
                try:
                    from planner.modules.datasets.public import get_dataset
                except (ImportError, AttributeError) as exc:
                    raise RuntimeError("datasets.public not implemented") from exc

                ds_info = await get_dataset(session, plan.dataset_id)
                if not ds_info or not getattr(ds_info, "ingested_object_key", None):
                    raise RuntimeError("Dataset or ingested_object_key not found")

                raw_bytes = await storage.get_object(ds_info.ingested_object_key)
                v0_key = f"snapshots/{plan_id}/v0.parquet"
                # v0 is IMMUTABLE — write once, never overwritten, never deleted
                await storage.put_object(v0_key, raw_bytes, "application/octet-stream")

                v0_row = PipelineVersion(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=0,
                    step_id=None,
                    snapshot_object_key=v0_key,
                    inverse_operation={"op": "v0_original"},
                    executed_by=None,
                )
                session.add(v0_row)
                await session.flush()

                with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_p = Path(tmp.name)
                try:
                    base_frame = read_parquet(tmp_p)
                finally:
                    if tmp_p.exists():
                        tmp_p.unlink()
            else:
                base_frame = await read_snapshot_frame(plan_uuid, 0)

            current = base_frame
            n = 1
            for step in steps:
                op_name = step["operation"]
                if op_name not in OPS:
                    raise RuntimeError(f"Unknown operation: {op_name}")

                op = OPS[op_name]
                schema = {c: str(dt) for c, dt in zip(current.columns, current.dtypes)}
                op.validate(step["parameters"], schema=schema)

                before = current
                after = op.apply(current, step["parameters"])
                inv = op.inverse(before, after, step["parameters"])
                # extract_tables runs on the PRE-apply frame: ops like expand_nested
                # consume their input column, so the nested data only exists before.
                side = op.extract_tables(before, step["parameters"])

                buf = io.BytesIO()
                after.write_parquet(buf)
                key = f"snapshots/{plan_id}/v{n}.parquet"
                await storage.put_object(key, buf.getvalue(), "application/octet-stream")

                for tname, tdf in side.items():
                    sbuf = io.BytesIO()
                    tdf.write_parquet(sbuf)
                    skey = f"snapshots/{plan_id}/v{n}__{tname}.parquet"
                    await storage.put_object(skey, sbuf.getvalue(), "application/octet-stream")

                # Carry forward the previous version's side tables so every
                # version's snapshot is complete (later steps don't re-emit them).
                if hasattr(storage, "list_keys"):
                    prev_prefix = f"snapshots/{plan_id}/v{n - 1}__"
                    for skey in await storage.list_keys(prev_prefix):
                        fname = skey.rsplit("/", 1)[-1].split("__", 1)[1]
                        tname = fname.removesuffix(".parquet")
                        if tname in side:
                            continue
                        data = await storage.get_object(skey)
                        new_key = f"snapshots/{plan_id}/v{n}__{tname}.parquet"
                        await storage.put_object(new_key, data, "application/octet-stream")

                step_id_val = step["id"]
                step_uuid = step_id_val if isinstance(step_id_val, UUID) else UUID(str(step_id_val))

                version_row = PipelineVersion(
                    id=uuid.uuid4(),
                    plan_id=plan_uuid,
                    version_no=n,
                    step_id=step_uuid,
                    snapshot_object_key=key,
                    inverse_operation={"op": inv.op, "parameters": inv.parameters},
                    executed_by=None,
                )
                session.add(version_row)

                await add_event(
                    session,
                    EventType.PLAN_STEP_EXECUTED.value,
                    PlanStepExecutedPayload(
                        plan_id=plan_uuid,
                        step_id=step_uuid,
                        step_no=step["step_no"],
                    ),
                )
                current = after
                n += 1

            final_version = n - 1
            await add_event(
                session,
                EventType.PLAN_EXECUTED.value,
                PlanExecutedPayload(
                    plan_id=plan_uuid,
                    version_no=final_version,
                ),
            )
            await session.commit()
            await record_audit(
                session=session,
                event_type="plan.executed",
                object_type="plan",
                object_id=plan_id,
                details={"versionNo": final_version, "steps": len(steps)},
            )

            try:
                from planner.core.realtime import publish_job_status

                await publish_job_status(
                    plan.dataset_id,
                    JobStatusPayload(
                        job_id=job_uuid,
                        type="execute_plan",
                        status="completed",
                        progress_pct=100.0,
                        message="Plan executed successfully",
                        plan_id=plan_uuid,
                    ),
                )
            except (NotImplementedError, Exception) as exc:  # noqa: BLE001 -- status publish is best-effort
                logger.warning("Failed to publish plan-executed status: %s", exc)

            send_task_eager_aware(
                "planner.run_validation",
                args=[str(plan_id), str(job_id), final_version],
                queue="validate",
            )
            return {"plan_id": plan_id, "versions": final_version}

        except Exception as exc:
            await session.rollback()
            try:
                await add_event(
                    session,
                    EventType.JOB_FAILED.value,
                    JobFailedPayload(
                        job_id=job_uuid,
                        error_code="EXECUTION_FAILED",
                        error_message=str(exc)[:500],
                    ),
                )
                await session.commit()
            except (NotImplementedError, Exception) as bookkeeping_exc:  # noqa: BLE001 -- failure bookkeeping is best-effort
                logger.warning("Failed to record job-failed event: %s", bookkeeping_exc)
            raise


@celery_app.task(
    name="planner.execute_plan",
    queue="execute",
    soft_time_limit=900,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3,
)
def execute_plan(plan_id: str, job_id: str) -> dict[str, Any]:
    """Execute decided steps of an approved plan sequentially."""
    return asyncio.run(_async_execute_plan(plan_id, job_id))


async def _async_rollback_plan(
    plan_id: str, job_id: str, to_version_no: int, reason: str
) -> dict[str, Any]:
    # Guard: to_version_no must be >= 0; never delete v0 (we only copy, never delete)
    if to_version_no < 0:
        raise RuntimeError("VERSION_NOT_FOUND: to_version_no must be >= 0")

    plan_uuid = UUID(plan_id)
    async with SessionLocal() as session:
        stmt = (
            select(PipelineVersion)
            .where(PipelineVersion.plan_id == plan_uuid)
            .order_by(PipelineVersion.version_no.asc())
        )
        res = await session.execute(stmt)
        versions = list(res.scalars().all())

        target = next((v for v in versions if v.version_no == to_version_no), None)
        if target is None:
            raise RuntimeError("VERSION_NOT_FOUND")

        from_no = max(v.version_no for v in versions)
        new_no = from_no + 1
        storage = get_storage()

        # Byte-identical restore: rollback restores the snapshot exactly
        data = await storage.get_object(target.snapshot_object_key)
        new_key = f"snapshots/{plan_id}/v{new_no}.parquet"
        await storage.put_object(new_key, data, "application/octet-stream")
        # FR-034: prove the restored snapshot is byte-identical to the target version.
        target_sha = hashlib.sha256(data).hexdigest()
        restored_sha = hashlib.sha256(await storage.get_object(new_key)).hexdigest()
        if restored_sha != target_sha:
            raise RuntimeError("ROLLBACK_VERIFY_FAILED: restored snapshot differs from target")

        # Copy side tables with prefix v{to}__ -> v{new}__
        side_prefix = f"snapshots/{plan_id}/v{to_version_no}__"
        if hasattr(storage, "list_keys"):
            side_keys = await storage.list_keys(side_prefix)
            for skey in side_keys:
                filename = skey.split("/")[-1]
                table_suffix = filename.split("__", 1)[1]
                sdata = await storage.get_object(skey)
                new_skey = f"snapshots/{plan_id}/v{new_no}__{table_suffix}"
                await storage.put_object(new_skey, sdata, "application/octet-stream")

        # Insert new PipelineVersion representing the rollback state
        new_version_row = PipelineVersion(
            id=uuid.uuid4(),
            plan_id=plan_uuid,
            version_no=new_no,
            step_id=None,
            snapshot_object_key=new_key,
            inverse_operation={
                "op": "rollback",
                "from": from_no,
                "to": to_version_no,
                "reason": reason,
                "sha256": restored_sha,
                "byteIdentical": True,
            },
            executed_by=None,
        )
        session.add(new_version_row)

        # Update RollbackRow completed_at
        r_stmt = (
            select(RollbackRow)
            .where(RollbackRow.plan_id == plan_uuid, RollbackRow.completed_at.is_(None))
            .order_by(RollbackRow.created_at.desc())
            .limit(1)
        )
        r_res = await session.execute(r_stmt)
        rollback_row = r_res.scalars().first()
        if rollback_row:
            rollback_row.completed_at = datetime.now(UTC)

        await add_event(
            session,
            EventType.ROLLBACK_COMPLETED.value,
            RollbackCompletedPayload(
                plan_id=plan_uuid,
                version_no=new_no,
            ),
        )
        await session.commit()
        await record_audit(
            session=session,
            event_type="rollback.completed",
            object_type="plan",
            object_id=plan_id,
            details={"fromVersion": from_no, "toVersion": to_version_no, "newVersion": new_no,
                     "sha256": restored_sha, "byteIdentical": True},
        )

        # Defensive realtime publish: not wired yet (no-op placeholder).

        return {
            "plan_id": plan_id,
            "from_version": from_no,
            "to_version": to_version_no,
            "new_version": new_no,
            "sha256": restored_sha,
            "byte_identical": True,
        }


@celery_app.task(
    name="planner.rollback_plan",
    queue="execute",
    soft_time_limit=900,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=3,
)
def rollback_plan(plan_id: str, job_id: str, to_version_no: int, reason: str) -> dict[str, Any]:
    """Roll back a plan to a previous version by replicating its snapshot."""
    return asyncio.run(_async_rollback_plan(plan_id, job_id, to_version_no, reason))
