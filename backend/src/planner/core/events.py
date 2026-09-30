"""Event names and Pydantic payloads - the contract source (Backend.md).

Event names and payloads are defined ONCE here and exported to
contracts/events/*.schema.json for the frontend and docs.
"""

from __future__ import annotations

import enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class EventPayload(BaseModel):
    """Base for all event payloads: camelCase on the wire (Backend.md)."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class EventType(str, enum.Enum):
    DATASET_UPLOADED = "dataset.uploaded"
    DATASET_INGESTED = "dataset.ingested"
    DATASET_PROFILED = "dataset.profiled"
    RULES_INFERRED = "rules.inferred"
    PLAN_REQUESTED = "plan.requested"
    PLAN_GENERATED = "plan.generated"
    PLAN_APPROVED = "plan.approved"
    PLAN_STEP_EXECUTED = "plan.step_executed"
    PLAN_EXECUTED = "plan.executed"
    VALIDATION_COMPLETED = "validation.completed"
    ROLLBACK_REQUESTED = "rollback.requested"
    ROLLBACK_COMPLETED = "rollback.completed"
    EVALUATION_REQUESTED = "evaluation.requested"
    EVALUATION_COMPLETED = "evaluation.completed"
    JOB_FAILED = "job.failed"
    JOB_STATUS = "job.status"


class DatasetUploadedPayload(EventPayload):
    dataset_id: UUID


class DatasetIngestedPayload(EventPayload):
    dataset_id: UUID


class DatasetProfiledPayload(EventPayload):
    dataset_id: UUID


class RulesInferredPayload(EventPayload):
    dataset_id: UUID
    rule_count: int


class PlanRequestedPayload(EventPayload):
    dataset_id: UUID


class PlanGeneratedPayload(EventPayload):
    plan_id: UUID


class PlanApprovedPayload(EventPayload):
    plan_id: UUID


class PlanStepExecutedPayload(EventPayload):
    plan_id: UUID
    step_id: UUID
    step_no: int


class PlanExecutedPayload(EventPayload):
    plan_id: UUID
    version_no: int


class ValidationCompletedPayload(EventPayload):
    plan_id: UUID
    version_no: int
    passed: bool


class RollbackRequestedPayload(EventPayload):
    plan_id: UUID
    from_version_no: int
    to_version_no: int


class RollbackCompletedPayload(EventPayload):
    plan_id: UUID
    version_no: int


class EvaluationRequestedPayload(EventPayload):
    benchmark_set_id: UUID


class EvaluationCompletedPayload(EventPayload):
    evaluation_id: UUID
    pass_rate: float


class JobFailedPayload(EventPayload):
    job_id: UUID
    error_code: str
    error_message: str


class JobStatusPayload(EventPayload):
    """SSE job.status message: { jobId, type, status, progressPct, message, planId? }."""

    job_id: UUID
    type: str
    status: str
    progress_pct: float = Field(ge=0, le=100)
    message: str
    plan_id: UUID | None = None


EVENT_PAYLOADS: dict[EventType, type[EventPayload]] = {
    EventType.DATASET_UPLOADED: DatasetUploadedPayload,
    EventType.DATASET_INGESTED: DatasetIngestedPayload,
    EventType.DATASET_PROFILED: DatasetProfiledPayload,
    EventType.RULES_INFERRED: RulesInferredPayload,
    EventType.PLAN_REQUESTED: PlanRequestedPayload,
    EventType.PLAN_GENERATED: PlanGeneratedPayload,
    EventType.PLAN_APPROVED: PlanApprovedPayload,
    EventType.PLAN_STEP_EXECUTED: PlanStepExecutedPayload,
    EventType.PLAN_EXECUTED: PlanExecutedPayload,
    EventType.VALIDATION_COMPLETED: ValidationCompletedPayload,
    EventType.ROLLBACK_REQUESTED: RollbackRequestedPayload,
    EventType.ROLLBACK_COMPLETED: RollbackCompletedPayload,
    EventType.EVALUATION_REQUESTED: EvaluationRequestedPayload,
    EventType.EVALUATION_COMPLETED: EvaluationCompletedPayload,
    EventType.JOB_FAILED: JobFailedPayload,
    EventType.JOB_STATUS: JobStatusPayload,
}


def event_schema(event: EventType) -> dict:
    """JSON Schema for one event payload (used to generate contracts/events/)."""
    model = EVENT_PAYLOADS[event]
    schema = model.model_json_schema(by_alias=True)
    schema["$id"] = f"https://png6.local/contracts/events/{event.value}.schema.json"
    schema["title"] = event.value
    return schema
