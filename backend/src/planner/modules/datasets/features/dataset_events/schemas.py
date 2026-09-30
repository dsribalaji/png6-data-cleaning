"""Schemas for dataset SSE events."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class DatasetEventData(BaseModel):
    """Payload streamed in each SSE event (camelCase on wire)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    job_id: UUID
    type: str
    status: str
    progress_pct: float = Field(ge=0.0, le=100.0)
    message: str
    plan_id: UUID | None = None
