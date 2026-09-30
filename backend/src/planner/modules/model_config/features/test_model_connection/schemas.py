"""Schemas for POST /model-config/test."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class TestModelConnectionInput(BaseModel):
    """Optional overrides for testing a model connection."""

    __test__ = False

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    provider: str | None = None
    model: str | None = None
    endpoint_url: str | None = None
    credential: str | None = None


class TestModelConnectionOut(BaseModel):
    """Response returned upon successful connection test."""

    __test__ = False

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    ok: bool = True
    latency_ms: int
