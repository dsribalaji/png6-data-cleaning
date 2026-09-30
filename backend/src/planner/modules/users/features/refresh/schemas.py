"""Schemas for token refresh (Backend.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class TokenResponse(BaseModel):
    """Token envelope returned after token refresh."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class RefreshResult(TokenResponse):
    """Internal service result containing new access token and rotated refresh token."""

    refresh_token: str
