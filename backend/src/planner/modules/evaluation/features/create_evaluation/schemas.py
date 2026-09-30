"""Pydantic schemas for create_evaluation slice."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class CreateEvaluationIn(BaseModel):
    """Input payload for creating an evaluation run."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    benchmark_set_id: UUID | None = None
    # Frontend S10 posts a benchmark-set *name* slug (e.g. "vendor-invoices-golden");
    # the service resolves it to an id. Accepts either form.
    benchmark_set: str | None = None
    model_config_id: UUID | None = None


class CreateEvaluationOut(BaseModel):
    """Response payload returned when evaluation run is accepted."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    id: UUID
    status: str
