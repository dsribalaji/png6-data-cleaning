"""Pydantic schemas for the execution module (Backend.md)."""

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


class VersionOut(CamelModel):
    version_no: int
    step_id: UUID | None = None
    created_at: datetime
    executed_by: UUID | None = None
    is_current: bool = False


class VersionsResponse(CamelModel):
    plan_id: UUID
    items: list[VersionOut]
    total: int


class RollbackRequest(CamelModel):
    to_version: int
    reason: str


class RollbackResponse(CamelModel):
    plan_id: UUID
    from_version: int
    to_version: int
    job_id: UUID


class ExportRequest(CamelModel):
    format: str = "xlsx"


class ExportResponse(CamelModel):
    download_url: str
    expires_at: datetime
