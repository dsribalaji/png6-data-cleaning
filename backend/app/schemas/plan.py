"""Cleaning plan and step schemas."""

from typing import Any, Literal
import uuid
from pydantic import BaseModel, Field

OpType = Literal[
    "replace_value",
    "fill_missing",
    "drop_column",
    "cast_type",
    "derive_column",
    "expand_nested",
    "deduplicate",
    "standardise_format",
]

DecisionType = Literal["approve", "reject", "edit"]


class LossEstimateOut(BaseModel):
    """Pre-execution loss impact estimate for a step."""

    rows_affected: int = Field(..., description="Estimated rows impacted")
    cols_affected: int = Field(..., description="Estimated columns impacted")
    cells_affected: int = Field(..., description="Estimated cells impacted")
    loss_pct: float = Field(..., description="Estimated loss percentage")
    held_for_approval: bool = Field(
        ...,
        description="Whether this step is held for manual approval (loss > 5% threshold)",
    )


class PlanStepIn(BaseModel):
    """Input payload to create or modify a plan step."""

    op_type: OpType = Field(..., description="One of the 8 allowed cleaning operations")
    params: dict[str, Any] = Field(default_factory=dict, description="Operation parameters")


class PlanStepOut(BaseModel):
    """Cleaning plan step representation."""

    id: uuid.UUID = Field(..., description="Unique step identifier")
    seq: int = Field(..., description="Sequence execution order")
    op_type: str = Field(..., description="Operation type")
    params: dict[str, Any] = Field(..., description="Operation parameters")
    status: str = Field(
        ...,
        description="Step status: proposed, approved, rejected, held, executed",
    )
    loss: LossEstimateOut | None = Field(
        default=None,
        description="Associated loss estimate",
    )


class PlanOut(BaseModel):
    """Complete cleaning plan with all steps and cumulative metrics."""

    id: uuid.UUID = Field(..., description="Unique plan identifier")
    dataset_id: uuid.UUID = Field(..., description="Associated dataset identifier")
    status: str = Field(
        ...,
        description="Plan status: draft, approved, executing, done, rolled_back",
    )
    steps: list[PlanStepOut] = Field(default_factory=list, description="Ordered plan steps")
    cumulative_loss_pct: float = Field(
        default=0.0,
        description="Cumulative projected data loss percentage across all steps",
    )


class ApprovalIn(BaseModel):
    """Plan approval decisions from user review."""

    decisions: dict[str, DecisionType] = Field(
        ...,
        description="Mapping of step ID string to decision ('approve', 'reject', or 'edit')",
    )
    edited_params: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Optional modified parameters for steps marked 'edit'",
    )
