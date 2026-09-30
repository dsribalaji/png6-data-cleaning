"""Schemas for upload configuration endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class UploadConfigResponse(BaseModel):
    """Configuration limits and allowed formats for uploads (camelCase on wire)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    max_file_mb: int
    allowed_extensions: list[str]
    loss_threshold_default: float
