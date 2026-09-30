"""Schemas for the invite_user use case (Backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["data_engineer", "administrator", "auditor", "viewer"]


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class InviteUserRequest(BaseModel):
    """Payload for inviting a new user."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    email: str = Field(..., min_length=3, max_length=320)
    role: Role


class InviteUserResponse(BaseModel):
    """One-time invite token handed to the invitee (sent by email in production)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    invite_token: str
    expires_at: datetime
