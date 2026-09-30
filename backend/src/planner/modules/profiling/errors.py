"""Profiling module error definitions (RFC 9457 problem+json, Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError


class ProfilingErrors:
    PROFILE_NOT_FOUND = AppError("PROFILE_NOT_FOUND", "No profile found for this dataset.", 404)
    RULES_NOT_FOUND = AppError("RULES_NOT_FOUND", "No inferred rules for this dataset.", 404)
