"""Deactivate user feature (administrator revokes access and refresh tokens)."""

from __future__ import annotations

from planner.modules.users.features.deactivate_user.router import router
from planner.modules.users.features.deactivate_user.service import deactivate_user_service

__all__ = ["deactivate_user_service", "router"]
