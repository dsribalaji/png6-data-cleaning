"""Error definitions for the validation module (Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError


class ValidationErrors:
    VALIDATION_NOT_FOUND = AppError(
        "VALIDATION_NOT_FOUND", "No validation results for this plan yet.", 404
    )
