"""Pydantic schemas for the export_audit_events feature slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class ExportAuditEventsInput(BaseModel):
    """Filter parameters for audit events CSV export (no pagination)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = Field(default=None, alias="to")
    event_type: str | None = Field(default=None, alias="eventType")
    user_id: UUID | None = Field(default=None, alias="userId")

    @model_validator(mode="before")
    @classmethod
    def _remap_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "from_time" in data and "from" not in data and "from_" not in data:
                data["from"] = data.pop("from_time")
            if "to_time" in data and "to" not in data:
                data["to"] = data.pop("to_time")
        return data

    @property
    def from_time(self) -> datetime | None:
        """Alias property for from_."""
        return self.from_

    @property
    def to_time(self) -> datetime | None:
        """Alias property for to."""
        return self.to


class ExportAuditEventsOut(BaseModel):
    """Result of audit events CSV export containing generated content and metadata."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    csv_content: str
    filename: str
    row_count: int

    @property
    def content(self) -> str:
        """Alias for csv_content."""
        return self.csv_content

    def __iter__(self) -> Any:
        """Allow tuple unpacking: csv_content, filename = result."""
        return iter((self.csv_content, self.filename))

    def __getitem__(self, item: Any) -> Any:
        """Allow indexed access: result[0], result[1]."""
        if isinstance(item, int):
            return (self.csv_content, self.filename)[item]
        return getattr(self, item)

    def __str__(self) -> str:
        """String representation returns the CSV content."""
        return self.csv_content
