"""Pydantic schemas for get_evaluation slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class GetEvaluationIn(BaseModel):
    """Input parameters for fetching an evaluation run."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    run_id: UUID


class EvaluationRunOut(BaseModel):
    """Evaluation run detail response envelope."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: UUID
    benchmark_set_id: UUID
    model_config_id: UUID | None = None
    status: str
    scores: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None


__all__ = ["EvaluationRunOut", "GetEvaluationIn", "_to_camel"]
