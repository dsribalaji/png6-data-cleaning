"""Schemas for accepting user invites (Backend.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class AcceptInviteRequest(BaseModel):
    """Payload for completing invitation registration."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    password: str = Field(..., min_length=12, max_length=128)
    first_name: str | None = None
    last_name: str | None = None


class TokenResponse(BaseModel):
    """Access token envelope returned after invite acceptance."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class AcceptInviteResult(TokenResponse):
    """Internal service result containing access token and auto-login refresh token."""

    refresh_token: str
