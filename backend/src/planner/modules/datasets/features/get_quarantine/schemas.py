"""Schemas for get_quarantine feature."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class QuarantineRecordRead(BaseModel):
    """Quarantine record response schema with camelCase wire serialization."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    dataset_id: UUID
    row_ref: str
    reason: str
    created_at: datetime
