"""Celery tasks for the planning module (Backend.md)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

import polars as pl
from pydantic import BaseModel
from sqlalchemy import select

from planner.core.db import SessionLocal
from planner.core.events import EventType, JobStatusPayload, PlanGeneratedPayload
from planner.core.outbox import add_event
from planner.core.ports.llm import LlmGatewayPort
from planner.engine.guards.scanner import mask_sample, scan_prompt_injection
from planner.engine.ingest.parquet import read_parquet
from planner.engine.loss.estimator import cumulative_loss, estimate_step_loss
from planner.engine.nested import summarise
from planner.engine.ops.base import OPS, LossEstimate
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep
from planner.worker import celery_app

logger = logging.getLogger(__name__)

# Steps below this confidence are never pre-accepted (Level 3 B5).
LOW_CONFIDENCE = 0.6


@dataclass
class StepCandidate:
    operation: str
    parameters: dict[str, Any]
    rationale: str
    confidence: float
    source: str = "deterministic"  # "llm" for AI-suggested steps (Level 3 B5)


def _llm_gateway() -> LlmGatewayPort:
    """The admin's saved model (else env vars), with the Redis cache (Level 3 B1)."""
    from planner.modules.model_config.public import build_llm_gateway

    return build_llm_gateway()


def _expand_rationale(cells: list[Any], column: str, child: str, key: str | None) -> str:
    """Say what expanding will recover and lose, cell by cell (engine/nested.py)."""
    c = summarise(cells)
    text = (
        f"Expand the nested records in '{column}' into a new table '{child}' "
        f"({c['items']:,} rows, linked by '{key}')."
    )
    if c["repaired"]:
        text += f" {c['repaired']:,} cells were not strict JSON (single quotes) and were repaired."
    if c["partial"]:
        text += (
            f" {c['partial']:,} cells were cut off: their complete items are kept, the cut-off"
            " item is lost."
        )
    if c["invalid"]:
        text += f" {c['invalid']:,} cells could not be read at all and are lost."
    return text


def merge_steps(
    deterministic: list[StepCandidate], llm: list[StepCandidate], df: pl.DataFrame
) -> tuple[list[StepCandidate], list[str]]:
    """Deterministic steps first; AI steps added when they target something new.

    Level 3 B4: an AI step enters the plan only if its parameters validate against the
    schema AND its loss can be estimated on the real data (a dry run of the operation).
    Returns the merged steps and a description of each AI step that was left out.
    """
    schema = {col: str(df.schema[col]) for col in df.columns}

    def key(c: StepCandidate) -> tuple[str, str]:
        return c.operation, str(c.parameters.get("column") or c.parameters.get("name") or "")

    final = list(deterministic)
    seen = {key(c) for c in deterministic}
    rejected: list[str] = []
    for c in llm:
        if key(c) in seen:
            continue
        try:
            if c.operation not in OPS:
                raise ValueError("not in the operation catalogue")
            OPS[c.operation].validate(c.parameters, schema)
            estimate_step_loss(df, c.operation, c.parameters)
        except Exception as exc:  # noqa: BLE001 -- LLM candidates are untrusted; invalid ones are recorded and skipped
            rejected.append(f"{c.operation}({key(c)[1] or '?'}): {str(exc)[:80]}")
            logger.info("llm step rejected: %s %s: %s", c.operation, c.parameters, exc)
            continue
        seen.add(key(c))
        final.append(c)
    return final, rejected


def default_decision(estimated_loss: float, threshold: float, confidence: float) -> str:
    """PRD S5 / FR-031: steps at or under the loss threshold start as Accept; steps above
    it, or with low confidence (Level 3 B5), wait for an explicit decision."""
    return "accepted" if estimated_loss <= threshold and confidence >= LOW_CONFIDENCE else "pending"


# Operations that invent a value the source data did not have. decision.md's P1
# (and B7 for cross-field fill) keeps these out of the automatic path: the FRS
# leaves fill-vs-null open at OQ-12, and the PowerBI guide's Step 4 shows what
# goes wrong when a value is assumed (a hardcoded date and invoice number), so a
# human decides every one of them.
NEVER_AUTO_ACCEPT: frozenset[str] = frozenset({"fill_missing", "derive_column"})


def step_decision(
    operation: str, estimated_loss: float, threshold: float, confidence: float
) -> str:
    """The decision for one proposed step, honouring the never-auto-accept rule.

    Kept separate from `default_decision` so the rule has one home and can be
    tested directly rather than only through a full plan run.
    """
    if operation in NEVER_AUTO_ACCEPT:
        return "pending"
    return default_decision(estimated_loss, threshold, confidence)


# Only catalogue operations (FR-022); the schema sent to the model lists them.
Operation = Literal[
    "replace_value",
    "fill_missing",
    "drop_column",
    "cast_type",
    "derive_column",
    "expand_nested",
    "deduplicate",
    "standardise_format",
]


class _ProposedStep(BaseModel):
    operation: Operation
    parameters: dict[str, Any]
    rationale: str
    confidence: float = 0.8


class _ProposedStepsOut(BaseModel):
    steps: list[_ProposedStep]


class _ProposeStepsPayload(BaseModel):
    table_name: str
    rules_summary: list[dict[str, Any]]
    column_summary: list[dict[str, Any]]
    samples: dict[str, list[str]]


async def _try_llm_steps(
    df: pl.DataFrame,
    rules: list[Any],
    columns_info: list[Any],
    table_name: str,
) -> tuple[list[StepCandidate], BaseException | None]:
    """LLM step proposals. Never raises: returns the steps and the exception, if any."""
    try:
        gateway = _llm_gateway()
        samples: dict[str, list[str]] = {}
        for c in columns_info:
            c_name = getattr(c, "column_name", None) or getattr(c, "name", None)
            if not c_name or c_name not in df.columns:
                continue
            series = df[c_name].drop_nulls()
            candidate_vals = [str(v) for v in series.head(10).to_list()]

            cells_to_scan = [(c_name, i, v) for i, v in enumerate(candidate_vals)]
            injections = scan_prompt_injection(cells_to_scan)
            flagged = {inj.value_preview for inj in injections}

            safe_samples: list[str] = []
            for v in candidate_vals:
                if any(v.startswith(f) for f in flagged):
                    continue
                safe_samples.append(mask_sample(v))
                if len(safe_samples) >= 5:
                    break
            samples[c_name] = safe_samples

        payload = _ProposeStepsPayload(
            table_name=table_name,
            rules_summary=[
                {
                    "rule_type": getattr(r, "rule_type", ""),
                    "columns": getattr(r, "columns", []),
                    "expression": getattr(r, "expression", {}),
                }
                for r in rules
            ],
            column_summary=[
                {
                    "name": getattr(c, "column_name", None) or getattr(c, "name", ""),
                    "semantic_type": getattr(c, "semantic_type", ""),
                    "flags": getattr(c, "flags", []) or [],
                }
                for c in columns_info
            ],
            samples=samples,
        )

        resp = await gateway.complete("propose_steps", payload, _ProposedStepsOut)
        candidates: list[StepCandidate] = []
        for s in resp.steps:
            if s.operation in OPS:
                candidates.append(
                    StepCandidate(
                        operation=s.operation,
                        parameters=s.parameters,
                        rationale=s.rationale,
                        confidence=float(s.confidence),
                        source="llm",
                    )
                )
        return candidates, None
    except Exception as exc:  # noqa: BLE001 -- LLM is non-blocking; the failure is returned to the caller
        return [], exc


def build_steps_from_rules(
    rules: list[Any],
    profile: Any,
    df: pl.DataFrame,
) -> list[StepCandidate]:
    """Pure deterministic function mapping inferred rules and profile to cleaning steps.

    Order:
      1. drop_column (all-null)
      2. cast_type (numeric_as_text)
      3. replace_value (entity_group)
      4. standardise_format (date)
      5. fill_missing (cross_field_fill)
      6. expand_nested (one_to_many)
      7. deduplicate (exact duplicates if any)
      8. drop_column (arithmetic redundant equality)
    """
    columns_info = getattr(profile, "columns", []) if profile else []
    schema = {col: str(df.schema[col]) for col in df.columns}

    # Helper: find primary key column
    pk_col = None
    for r in rules:
        if getattr(r, "rule_type", None) == "primary_key":
            cols = getattr(r, "columns", [])
            expr = getattr(r, "expression", {})
            pk_col = expr.get("column") or (cols[0] if cols else None)
            if pk_col:
                break
    if not pk_col:
        # No unique key inferred: link child rows on the identifier-typed column with
        # the most distinct values (FR-050: chosen from the profile, never by name).
        identifiers = [
            c
            for c in columns_info
            if getattr(c, "semantic_type", "") == "identifier"
            and (getattr(c, "column_name", None) or getattr(c, "name", None)) in df.columns
        ]
        if identifiers:
            best = max(identifiers, key=lambda c: getattr(c, "distinct_count", 0) or 0)
            pk_col = getattr(best, "column_name", None) or getattr(best, "name", None)
        elif df.columns:
            pk_col = df.columns[0]
        else:
            pk_col = "_row"

    # 1. drop_column (all-null)
    drop_null_steps: list[StepCandidate] = []
    seen_drop_cols: set[str] = set()
    for col in columns_info:
        c_name = getattr(col, "column_name", None) or getattr(col, "name", None)
        flags = getattr(col, "flags", []) or []
        sem_type = getattr(col, "semantic_type", "")
        if c_name in df.columns and (
            "all_null" in flags or (sem_type == "unknown" and "all_null" in flags)
        ):
            drop_null_steps.append(
                StepCandidate(
                    operation="drop_column",
                    parameters={"column": c_name},
                    rationale=f"Drop all-null column '{c_name}'",
                    confidence=1.0,
                )
            )
            seen_drop_cols.add(c_name)

    # 2. cast_type (numeric_as_text)
    cast_steps: list[StepCandidate] = []
    for col in columns_info:
        c_name = getattr(col, "column_name", None) or getattr(col, "name", None)
        flags = getattr(col, "flags", []) or []
        if c_name in df.columns and "numeric_as_text" in flags and c_name not in seen_drop_cols:
            cast_steps.append(
                StepCandidate(
                    operation="cast_type",
                    parameters={"column": c_name, "dtype": "float", "strip_chars": "$, "},
                    rationale=f"Cast numeric text column '{c_name}' to float",
                    confidence=0.95,
                )
            )

    # 3. replace_value (entity_group)
    replace_steps: list[StepCandidate] = []
    for r in rules:
        if getattr(r, "rule_type", None) == "entity_group":
            cols = getattr(r, "columns", [])
            expr = getattr(r, "expression", {})
            c_name = expr.get("column") or (cols[0] if cols else None)
            if not c_name or c_name not in df.columns or c_name in seen_drop_cols:
                continue
            groups = expr.get("groups", [])
            mapping: dict[str, str] = {}
            for grp in groups:
                canonical = grp.get("canonical")
                variants = grp.get("variants", [])
                for v in variants:
                    if v != canonical:
                        mapping[v] = canonical
            if mapping:
                replace_steps.append(
                    StepCandidate(
                        operation="replace_value",
                        parameters={"column": c_name, "mapping": mapping},
                        rationale=f"Standardise entity values in '{c_name}' using canonical names",
                        confidence=float(getattr(r, "confidence", 0.9)),
                    )
                )

    # 4. standardise_format (date)
    standardise_steps: list[StepCandidate] = []
    seen_date_cols: set[str] = set()
    for col in columns_info:
        c_name = getattr(col, "column_name", None) or getattr(col, "name", None)
        sem_type = getattr(col, "semantic_type", "")
        if c_name in df.columns and sem_type == "date" and c_name not in seen_drop_cols:
            standardise_steps.append(
                StepCandidate(
                    operation="standardise_format",
                    parameters={"column": c_name, "format": "iso_date"},
                    rationale=f"Standardise date format in '{c_name}' to ISO date",
                    confidence=0.95,
                )
            )
            seen_date_cols.add(c_name)

    # 5. fill_missing (cross_field_fill)
    fill_steps: list[StepCandidate] = []
    for r in rules:
        if getattr(r, "rule_type", None) == "cross_field_fill":
            expr = getattr(r, "expression", {})
            target = expr.get("target")
            source = expr.get("source")
            val = expr.get("value")
            if target and target in df.columns and target not in seen_drop_cols:
                fill_steps.append(
                    StepCandidate(
                        operation="fill_missing",
                        parameters={"column": target, "value": val},
                        rationale=f"Fill missing values in '{target}' from source '{source}'",
                        confidence=float(getattr(r, "confidence", 0.8)),
                    )
                )

    # 6. expand_nested (one_to_many)
    # Only columns the profile found to hold nested JSON can be expanded. A one-to-many
    # rule between two plain columns (the AI infers e.g. supplier -> invoices) is a
    # relationship, not nesting; expanding it gives an empty child table, fails its
    # generated test and blocks export.
    nested_cols = {
        getattr(c, "column_name", None) or getattr(c, "name", None)
        for c in columns_info
        if getattr(c, "semantic_type", "") == "nested_json"
        or "nested_json" in (getattr(c, "flags", None) or [])
    }
    nested_steps: list[StepCandidate] = []
    for r in rules:
        if getattr(r, "rule_type", None) == "one_to_many":
            cols = getattr(r, "columns", [])
            expr = getattr(r, "expression", {})
            c_name = cols[0] if cols else expr.get("column")
            if not c_name or c_name not in df.columns or c_name in seen_drop_cols:
                continue
            if c_name not in nested_cols:
                continue
            child_tbl = expr.get("child_table") or "".join(
                p.capitalize() for p in c_name.split("_") if p
            )
            nested_steps.append(
                StepCandidate(
                    operation="expand_nested",
                    parameters={"column": c_name, "key_column": pk_col, "child_table": child_tbl},
                    rationale=_expand_rationale(df[c_name].to_list(), c_name, child_tbl, pk_col),
                    confidence=float(getattr(r, "confidence", 0.95)),
                )
            )

    # 7. deduplicate
    dedup_steps: list[StepCandidate] = []
    if len(df) > 0 and df.is_duplicated().sum() > 0:
        dedup_steps.append(
            StepCandidate(
                operation="deduplicate",
                parameters={"subset": None},
                rationale="Deduplicate exact matching rows",
                confidence=1.0,
            )
        )

    # 8. arithmetic (redundant drop last)
    arithmetic_drop_steps: list[StepCandidate] = []
    for r in rules:
        if getattr(r, "rule_type", None) == "arithmetic":
            expr = getattr(r, "expression", {})
            if expr.get("kind") == "equality":
                target = expr.get("target")
                formula = expr.get("formula")
                if target and target in df.columns and target not in seen_drop_cols:
                    arithmetic_drop_steps.append(
                        StepCandidate(
                            operation="drop_column",
                            parameters={"column": target, "redundant_with": formula},
                            rationale=f"redundant: equals {formula} on all rows",
                            confidence=float(getattr(r, "confidence", 1.0)),
                        )
                    )
                    seen_drop_cols.add(target)

    # Combine in canonical order
    candidates = (
        drop_null_steps
        + cast_steps
        + replace_steps
        + standardise_steps
        + fill_steps
        + nested_steps
        + dedup_steps
        + arithmetic_drop_steps
    )

    # Validate each candidate via OPS
    valid_candidates: list[StepCandidate] = []
    for cand in candidates:
        if cand.operation not in OPS:
            continue
        try:
            OPS[cand.operation].validate(cand.parameters, schema)
            valid_candidates.append(cand)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Skipping invalid candidate step %s with params %s: %s",
                cand.operation,
                cand.parameters,
                exc,
            )

    return valid_candidates


async def _generate_plan_impl(
    dataset_id_str: str, job_id_str: str, plan_id_str: str
) -> dict[str, Any]:
    dataset_id = UUID(dataset_id_str)
    job_id = UUID(job_id_str)
    plan_id = UUID(plan_id_str)

    async with SessionLocal() as session:
        # Idempotency check: if PlanStep rows already exist for this plan -> skip
        existing_step = await session.execute(
            select(PlanStep).where(PlanStep.plan_id == plan_id).limit(1)
        )
        if existing_step.scalar_one_or_none() is not None:
            return {"status": "already_done", "plan_id": plan_id_str}

        # Lazy cross-module imports
        try:
            from planner.modules.datasets.public import get_dataset
        except ImportError as err:
            raise RuntimeError("datasets.public not implemented") from err

        try:
            from planner.modules.execution.public import get_storage
        except ImportError as err:
            raise RuntimeError("execution.public not implemented") from err

        from planner.modules.profiling.public import (
            get_column_profile_rows,
            get_profile_run,
            list_rule_rows,
        )

        plan = await session.get(Plan, plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        # Load profile and rules
        _profile_run = await get_profile_run(session, dataset_id)
        column_rows = await get_column_profile_rows(session, dataset_id)
        rule_rows = await list_rule_rows(session, dataset_id)

        # Resolve ingested object key
        ds_info = await get_dataset(session, dataset_id)
        if ds_info is None or not getattr(ds_info, "ingested_object_key", None):
            raise ValueError(f"Dataset {dataset_id} missing ingested_object_key")

    # Load dataframe via storage
    storage = get_storage()
    key = ds_info.ingested_object_key
    if hasattr(storage, "get"):
        data = await storage.get(key)
    else:
        data = await storage.get_object(key)

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        df = read_parquet(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Build deterministic steps. NOTE: pass the column profile ROWS as the
    # profile's columns — ProfileRun itself has no per-column data.
    _profile_ns = type("ProfileNS", (), {"columns": column_rows, "issues": []})()
    deterministic_steps = build_steps_from_rules(
        rules=rule_rows,
        profile=_profile_ns,
        df=df,
    )

    # Attempt LLM steps
    llm_steps, llm_exc = await _try_llm_steps(
        df=df,
        rules=rule_rows,
        columns_info=column_rows,
        table_name=getattr(ds_info, "name", "dataset"),
    )

    final_steps, rejected = merge_steps(deterministic_steps, llm_steps, df)

    from planner.modules.model_config.public import describe_llm_outcome

    ai_status, ai_message = describe_llm_outcome(llm_exc)
    if ai_status == "used" and rejected:
        ai_message = (
            f"{len(rejected)} AI-suggested step(s) were invalid and left out: "
            + "; ".join(rejected[:5])
        )

    # Compute loss per step on df
    step_losses: list[LossEstimate] = []
    for s in final_steps:
        try:
            loss = estimate_step_loss(df, s.operation, s.parameters)
        except Exception as exc:  # noqa: BLE001 -- loss estimation is best-effort; default to zero loss
            logger.warning(
                "Loss estimation failed for op %s; defaulting to zero: %s",
                s.operation,
                exc,
            )
            loss = LossEstimate(
                op=s.operation,
                rows_affected=0,
                columns_affected=0,
                cells_affected=0,
                cells_affected_pct=0.0,
                estimated_loss=0.0,
            )
        step_losses.append(loss)

    total_loss = cumulative_loss(step_losses)

    # Write steps, loss estimates, and update plan
    async with SessionLocal() as session:
        db_plan = await session.get(Plan, plan_id)
        if db_plan:
            db_plan.total_estimated_loss = total_loss
            db_plan.ai_status, db_plan.ai_message = ai_status, ai_message
        threshold = (
            float(db_plan.loss_threshold)
            if db_plan and db_plan.loss_threshold is not None
            else 0.05
        )

        for i, (cand, loss) in enumerate(zip(final_steps, step_losses), start=1):
            step_row = PlanStep(
                plan_id=plan_id,
                step_no=i,
                operation=cand.operation,
                parameters=cand.parameters,
                rationale=cand.rationale,
                confidence=cand.confidence,
                source=cand.source,
                decision=step_decision(
                    cand.operation, loss.estimated_loss, threshold, cand.confidence
                ),
            )
            session.add(step_row)
            await session.flush()

            loss_row = LossEstimateRow(
                step_id=step_row.id,
                rows_affected=loss.rows_affected,
                columns_affected=loss.columns_affected,
                cells_affected=loss.cells_affected,
                estimated_loss=loss.estimated_loss,
            )
            session.add(loss_row)

        await add_event(
            session,
            EventType.PLAN_GENERATED,
            PlanGeneratedPayload(plan_id=plan_id),
        )
        await session.commit()
        if ai_status == "failed":
            from planner.core.audit import record_audit

            await record_audit(
                session=session,
                event_type="llm.failed",
                object_type="plan",
                object_id=str(plan_id),
                details={"task": "propose_steps", "message": ai_message},
            )

    # Defensive realtime notification
    try:
        from planner.core.realtime import publish_job_status

        await publish_job_status(
            dataset_id,
            JobStatusPayload(
                job_id=job_id,
                type="plan",
                status="completed",
                progress_pct=100.0,
                message=f"Plan generated ({len(final_steps)} steps, cumulative loss: {total_loss:.3f})",
                plan_id=plan_id,
            ),
        )
    except (NotImplementedError, Exception) as exc:  # noqa: BLE001 -- realtime notification is best-effort
        logger.warning("Failed to publish plan-generated status: %s", exc)

    return {"plan_id": plan_id_str, "steps": len(final_steps)}


@celery_app.task(
    name="planner.generate_plan",
    queue="plan",
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def generate_plan(dataset_id: str, job_id: str, plan_id: str) -> dict[str, Any]:
    """Celery task entrypoint for generating a cleaning plan."""
    return asyncio.run(_generate_plan_impl(dataset_id, job_id, plan_id))
