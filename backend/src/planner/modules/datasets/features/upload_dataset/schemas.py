"""Pydantic schemas for dataset upload and dataset representation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class DatasetRead(BaseModel):
    """Dataset response model with camelCase wire serialization."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    name: str
    source: str
    file_name: str
    row_count: int | None = None
    column_count: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    raw_object_key: str | None = None
    ingested_at: datetime | None = None
    uploaded_by: UUID | None = None
    version: int = 1
