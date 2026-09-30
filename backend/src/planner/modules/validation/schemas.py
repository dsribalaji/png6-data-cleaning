"""Pydantic schemas for the validation module (Backend.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization on the wire."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class TestRunOut(CamelModel):
    phase: str
    result: str
    detail: str
    run_at: datetime


class TestCaseOut(CamelModel):
    id: UUID
    name: str
    type: str
    target_step_id: UUID | None = None
    latest_run: TestRunOut | None = None


class ReconciliationOut(CamelModel):
    check_name: str
    source_value: str
    output_value: str
    ok: bool


class ValidationResponse(CamelModel):
    plan_id: UUID
    version_no: int
    passed: bool
    test_cases: list[TestCaseOut]
    reconciliation: list[ReconciliationOut]
