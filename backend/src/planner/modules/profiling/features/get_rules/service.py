"""Service implementation for get_rules feature."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.modules.profiling.errors import ProfilingErrors
from planner.modules.profiling.models import InferredRuleRow
from planner.modules.profiling.schemas import RuleOut, RulesResponse


async def get_rules(session: AsyncSession, dataset_id: UUID) -> RulesResponse:
    """Retrieve all inferred rules for a dataset, ordered by confidence descending."""
    stmt = (
        select(InferredRuleRow)
        .where(InferredRuleRow.dataset_id == dataset_id)
        .order_by(InferredRuleRow.confidence.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        raise ProfilingErrors.RULES_NOT_FOUND

    # Record audit defensively
    try:
        await record_audit(
            event_type="dataset.rules_viewed",
            object_type="dataset",
            object_id=str(dataset_id),
            details={"rule_count": len(rows)},
        )
    except (NotImplementedError, Exception):
        # Audit sink not implemented yet
        pass

    items = [
        RuleOut(
            id=row.id,
            rule_type=row.rule_type,
            columns=row.columns,
            expression=row.expression,
            confidence=float(row.confidence),
            evidence=row.evidence_rows if isinstance(row.evidence_rows, dict) else {},
            source=row.source,
        )
        for row in rows
    ]

    return RulesResponse(
        dataset_id=dataset_id,
        items=items,
        total=len(items),
    )
