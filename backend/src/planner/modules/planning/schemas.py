"""Pydantic schemas for the planning module (camelCase on wire, Backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class LossEstimateOut(CamelModel):
    rows_affected: int
    columns_affected: int
    cells_affected: int
    estimated_loss: float


class PlanStepOut(CamelModel):
    id: UUID
    step_no: int
    operation: str
    parameters: dict[str, Any]
    rationale: str
    confidence: float
    decision: str
    decision_reason: str | None = None
    estimated_loss: LossEstimateOut | None = None


class PlanOut(CamelModel):
    id: UUID
    dataset_id: UUID
    status: str
    total_estimated_loss: float
    loss_threshold: float
    steps: list[PlanStepOut] = Field(default_factory=list)
    created_at: datetime


class CreatePlanRequest(CamelModel):
    loss_threshold: float = 0.05


class DecideStepRequest(CamelModel):
    decision: str
    parameters: dict[str, Any] | None = None
    reason: str | None = None


class ApproveResponse(CamelModel):
    plan_id: UUID
    status: str
    job_id: UUID
