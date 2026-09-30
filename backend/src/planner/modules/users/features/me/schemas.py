"""Schemas for the me use case (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class UserRead(BaseModel):
    """User representation serialized in camelCase for the API."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    status: str
    role: str | None = None
