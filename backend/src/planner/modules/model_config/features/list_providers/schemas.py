"""Schemas for GET /model-config/providers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class ProviderInfoOut(BaseModel):
    """Metadata for a supported LLM provider."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    id: str
    label: str
    default_model: str
    needs_endpoint: bool
    needs_key: bool
    recommended: bool
