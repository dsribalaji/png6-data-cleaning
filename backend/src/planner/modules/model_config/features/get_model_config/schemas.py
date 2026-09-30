"""Schemas for GET /model-config."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class ModelConfigOut(BaseModel):
    """Active model configuration response (never leaks credentials)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    provider: str
    model: str
    endpoint_url: str | None = None
    credential_last4: str | None = None
    allow_data_sharing: bool = False
    is_active: bool = False
    updated_at: datetime
