"""Celery tasks for the profiling module (Backend.md)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import tempfile
from typing import Any
from uuid import UUID

import polars as pl
from pydantic import BaseModel, Field
from sqlalchemy import select

from planner.core.db import SessionLocal
from planner.core.events import (
    DatasetProfiledPayload,
    EventType,
    JobStatusPayload,
    RulesInferredPayload,
)
from planner.core.outbox import add_event
from planner.core.ports.llm import LlmGatewayPort
from planner.engine.guards.scanner import mask_sample, scan_prompt_injection
from planner.engine.infer.rules import InferredRule, infer_rules
from planner.engine.ingest.parquet import read_parquet
from planner.engine.profile.profiler import ColumnProfile, TableProfile, profile_table
from planner.modules.profiling.models import ColumnProfileRow, InferredRuleRow, ProfileRun
from planner.worker import celery_app, send_task_eager_aware

KNOWN_RULE_TYPES = {
    "entity_group",
    "arithmetic",
    "primary_key",
    "one_to_many",
    "semantic_type",
    "cross_field_fill",
}


@dataclass
class DatasetRef:
    """Internal dataset reference resolved from datasets.public."""

    id: UUID
    ingested_object_key: str


def _llm_gateway() -> LlmGatewayPort | None:
    """Single sanctioned composition point for LLM gateway.

    Lazily imports planner.llm.gateway.LlmGateway, returning None on any failure
    (e.g. gateway not implemented, missing API key, etc.).
    """
    try:
        from planner.llm.gateway import LlmGateway

        return LlmGateway()
    except Exception:
        return None


class _ColumnMeta(BaseModel):
    name: str
    semantic_type: str
    null_pct: float
    distinct_count: int


class _InferRulesPayload(BaseModel):
    table_name: str
    columns: list[_ColumnMeta]
    samples: dict[str, list[str]]


class _RuleOut(BaseModel):
    rule_type: str
    columns: list[str]
    expression: dict[str, Any]
    confidence: float = 0.8
    evidence: dict[str, Any] = Field(default_factory=dict)


class _RulesOut(BaseModel):
    rules: list[_RuleOut]


async def _try_llm_rules(df: pl.DataFrame, profile: TableProfile) -> list[InferredRule]:
    """Invoke LLM gateway for semantic rule inference with strict data minimisation."""
    gateway = _llm_gateway()
    if gateway is None:
        return []

    try:
        # Data minimisation: <= 5 samples per column, prompt injection scanning, masking
        samples: dict[str, list[str]] = {}
        for col in profile.columns:
            if col.name not in df.columns:
                continue
            series = df[col.name].drop_nulls()
            candidate_vals = [str(v) for v in series.head(10).to_list()]

            # Pre-scan for prompt injection
            cells_to_scan = [(col.name, i, v) for i, v in enumerate(candidate_vals)]
            injections = scan_prompt_injection(cells_to_scan)
            flagged_previews = {inj.value_preview for inj in injections}

            safe_samples: list[str] = []
            for v in candidate_vals:
                if any(v.startswith(flagged) for flagged in flagged_previews):
                    continue
                safe_samples.append(mask_sample(v))
                if len(safe_samples) >= 5:
                    break
            samples[col.name] = safe_samples

        payload = _InferRulesPayload(
            table_name=profile.table_name,
            columns=[
                _ColumnMeta(
                    name=c.name,
                    semantic_type=c.semantic_type,
                    null_pct=c.null_pct,
                    distinct_count=c.distinct_count,
                )
                for c in profile.columns
            ],
            samples=samples,
        )

        resp = await gateway.complete("infer_rules", payload, _RulesOut)
        rules: list[InferredRule] = []
        for r in resp.rules:
            if r.rule_type not in KNOWN_RULE_TYPES:
                continue
            rules.append(
                InferredRule(
                    rule_type=r.rule_type,
                    columns=r.columns,
                    expression=r.expression,
                    confidence=float(r.confidence),
                    evidence=r.evidence,
                    source="llm",
                )
            )
        return rules
    except Exception:
        # LLM failure must never break the deterministic pipeline
        return []


async def _load_parquet_frame(dataset_id: UUID) -> tuple[pl.DataFrame, str]:
    """Helper to resolve storage and load the ingested parquet dataframe."""
    try:
        from planner.modules.datasets.public import get_dataset
    except ImportError as err:
        raise RuntimeError("datasets.public not implemented") from err

    try:
        from planner.modules.execution.public import get_storage
    except ImportError as err:
        raise RuntimeError("execution.public not implemented") from err

    async with SessionLocal() as session:
        ds_info = await get_dataset(session, dataset_id)

    if ds_info is None or not getattr(ds_info, "ingested_object_key", None):
        raise ValueError(f"Dataset {dataset_id} not found or missing ingested_object_key")

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

    ds_name = getattr(ds_info, "name", "dataset")
    return df, ds_name


async def _profile_dataset_impl(dataset_id_str: str, job_id_str: str) -> dict[str, Any]:
    dataset_id = UUID(dataset_id_str)
    job_id = UUID(job_id_str)

    async with SessionLocal() as session:
        # Idempotency check
        existing = await session.execute(
            select(ProfileRun).where(ProfileRun.dataset_id == dataset_id)
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "already_done", "dataset_id": dataset_id_str}

    # Load dataframe from storage
    df, table_name = await _load_parquet_frame(dataset_id)
    profile = profile_table(df, table_name=table_name)

    async with SessionLocal() as session:
        run_row = ProfileRun(
            dataset_id=dataset_id,
            row_count=profile.row_count,
            column_count=profile.column_count,
            issues=profile.issues,
        )
        session.add(run_row)

        for col in profile.columns:
            col_row = ColumnProfileRow(
                dataset_id=dataset_id,
                column_name=col.name,
                ordinal=col.ordinal,
                physical_type=col.physical_type,
                semantic_type=col.semantic_type,
                null_count=col.null_count,
                null_pct=col.null_pct,
                distinct_count=col.distinct_count,
                min_value=col.min_value,
                max_value=col.max_value,
                mean_value=col.mean_value,
                flags=col.flags,
            )
            session.add(col_row)

        await add_event(
            session,
            EventType.DATASET_PROFILED,
            DatasetProfiledPayload(dataset_id=dataset_id),
        )
        await session.commit()

    # Defensive realtime notification
    try:
        from planner.core.realtime import publish_job_status

        await publish_job_status(
            dataset_id,
            JobStatusPayload(
                job_id=job_id,
                type="profile",
                status="running",
                progress_pct=50.0,
                message="Profile complete, inferring rules",
            ),
        )
    except (NotImplementedError, Exception):
        pass

    # Update dataset status BEFORE chaining (integration 2026-09-30: the
    # infer task sets 'ready_for_plan' after; doing this after the chain
    # would overwrite it).
    try:
        from planner.modules.datasets.public import update_dataset_status

        async with SessionLocal() as session:
            await update_dataset_status(session, dataset_id, "profiled")
            await session.commit()
    except (NotImplementedError, Exception):
        pass

    # Chain next task: planner.infer_rules
    send_task_eager_aware("planner.infer_rules", args=[dataset_id_str, job_id_str], queue="profile")

    return {"dataset_id": dataset_id_str, "columns": len(profile.columns)}


@celery_app.task(
    name="planner.profile_dataset",
    queue="profile",
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def profile_dataset(dataset_id: str, job_id: str) -> dict[str, Any]:
    """Celery task entrypoint for profiling a dataset."""
    return asyncio.run(_profile_dataset_impl(dataset_id, job_id))


async def _infer_rules_impl(dataset_id_str: str, job_id_str: str) -> dict[str, Any]:
    dataset_id = UUID(dataset_id_str)
    job_id = UUID(job_id_str)

    async with SessionLocal() as session:
        # Idempotency check
        existing = await session.execute(
            select(InferredRuleRow).where(InferredRuleRow.dataset_id == dataset_id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "already_done", "dataset_id": dataset_id_str}

    # Load dataframe and profile
    df, table_name = await _load_parquet_frame(dataset_id)
    profile = profile_table(df, table_name=table_name)

    # Deterministic heuristics
    deterministic_rules = infer_rules(df, profile)

    # LLM extra rules (non-blocking)
    llm_rules = await _try_llm_rules(df, profile)

    # Merge and deduplicate by (rule_type, tuple(columns))
    seen_keys: set[tuple[str, tuple[str, ...]]] = set()
    merged: list[tuple[InferredRule, str | None]] = []

    for r in deterministic_rules:
        k = (r.rule_type, tuple(r.columns))
        if k not in seen_keys:
            seen_keys.add(k)
            merged.append((r, None))

    for r in llm_rules:
        k = (r.rule_type, tuple(r.columns))
        if k not in seen_keys:
            seen_keys.add(k)
            merged.append((r, "infer_rules.v1"))

    async with SessionLocal() as session:
        for rule, p_version in merged:
            row = InferredRuleRow(
                dataset_id=dataset_id,
                rule_type=rule.rule_type,
                columns=rule.columns,
                expression=rule.expression,
                confidence=rule.confidence,
                evidence_rows=rule.evidence,
                source=rule.source,
                prompt_version=p_version,
            )
            session.add(row)

        await add_event(
            session,
            EventType.RULES_INFERRED,
            RulesInferredPayload(dataset_id=dataset_id, rule_count=len(merged)),
        )
        await session.commit()

    # Defensive realtime notification
    try:
        from planner.core.realtime import publish_job_status

        await publish_job_status(
            dataset_id,
            JobStatusPayload(
                job_id=job_id,
                type="profile",
                status="completed",
                progress_pct=100.0,
                message=f"Rules inferred ({len(merged)} rules)",
            ),
        )
    except (NotImplementedError, Exception):
        pass

    # Update dataset status defensively
    try:
        from planner.modules.datasets.public import update_dataset_status

        async with SessionLocal() as session:
            await update_dataset_status(session, dataset_id, "ready_for_plan")
            await session.commit()
    except (NotImplementedError, Exception):
        pass

    # Mark the profile job as succeeded (integration 2026-09-30)
    try:
        from planner.modules.datasets.public import update_job

        async with SessionLocal() as session:
            await update_job(session, job_id, status="succeeded", progress_pct=100.0)
            await session.commit()
    except Exception:
        pass

    return {"rules": len(merged)}


@celery_app.task(
    name="planner.infer_rules",
    queue="profile",
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def infer_rules_task(dataset_id: str, job_id: str) -> dict[str, Any]:
    """Celery task entrypoint for inferring rules."""
    return asyncio.run(_infer_rules_impl(dataset_id, job_id))
