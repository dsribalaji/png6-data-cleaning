"""Error definitions for the execution module (Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError


class ExecutionErrors:
    PLAN_NOT_FOUND = AppError("PLAN_NOT_FOUND", "Plan not found.", 404)
    VERSION_NOT_FOUND = AppError("VERSION_NOT_FOUND", "Version not found.", 404)
    REASON_REQUIRED = AppError(
        "REASON_REQUIRED", "Enter a reason of at least 10 characters.", 400
    )
    EXPORT_BLOCKED_TESTS_FAILED = AppError(
        "EXPORT_BLOCKED_TESTS_FAILED",
        "Export is blocked because 1 or more tests failed.",
        409,
    )
    NO_EXECUTED_VERSION = AppError(
        "NO_EXECUTED_VERSION", "The plan has no executed version yet.", 409
    )
    PLAN_NOT_APPROVED = AppError(
        "PLAN_NOT_APPROVED", "Only an approved plan can be executed.", 409
    )
