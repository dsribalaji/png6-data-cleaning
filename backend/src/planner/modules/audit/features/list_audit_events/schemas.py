"""Pydantic schemas for the list_audit_events feature slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class AuditEventOut(BaseModel):
    """Output representation of a single audit event."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    occurred_at: datetime
    user_id: UUID | None = None
    user_role: str | None = None
    event_type: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class ListAuditEventsInput(BaseModel):
    """Filter and pagination parameters for listing audit events."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = Field(default=None, alias="to")
    event_type: str | None = Field(default=None, alias="eventType")
    user_id: UUID | None = Field(default=None, alias="userId")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100, alias="pageSize")

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
