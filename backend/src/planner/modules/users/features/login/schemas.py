"""Schemas for user login (Backend.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class LoginRequest(BaseModel):
    """Payload for user authentication."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    email: str
    password: str


class TokenResponse(BaseModel):
    """Access token envelope returned on successful login or refresh."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class LoginResult(TokenResponse):
    """Internal service result containing access token and opaque refresh token."""

    refresh_token: str
