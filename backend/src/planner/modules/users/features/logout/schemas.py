"""Schemas for logout (Backend.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class LogoutResponse(BaseModel):
    """Logout response message envelope."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    message: str = "Logged out successfully"
