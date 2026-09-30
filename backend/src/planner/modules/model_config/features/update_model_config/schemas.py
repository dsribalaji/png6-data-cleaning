"""Schemas for PUT /model-config."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from planner.modules.model_config.features.get_model_config.schemas import ModelConfigOut


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class UpdateModelConfigInput(BaseModel):
    """Payload to update or initialize the active model configuration."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    provider: str
    model: str
    endpoint_url: str | None = None
    credential: str | None = None
    allow_data_sharing: bool = False


__all__ = ["UpdateModelConfigInput", "ModelConfigOut"]
