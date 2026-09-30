"""Schemas for the list_users use case (Backend.md).

``UserRead`` is the canonical user projection and is re-exported here so the
administrator slices share one shape with ``GET /auth/me``.
"""

from __future__ import annotations

from planner.core.pagination import Page
from planner.modules.users.features.me.schemas import UserRead

__all__ = ["Page", "UserRead"]
