"""Schemas for the change_role use case (Backend.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from planner.modules.users.features.me.schemas import UserRead

Role = Literal["data_engineer", "administrator", "auditor", "viewer"]


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class ChangeRoleRequest(BaseModel):
    """Payload carrying the single replacement role (one role per user, OQ-21)."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    role: Role


__all__ = ["ChangeRoleRequest", "UserRead"]
