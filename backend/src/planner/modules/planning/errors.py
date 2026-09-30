"""Planning module error definitions (RFC 9457 problem+json, Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError


class PlanningErrors:
    PLAN_NOT_FOUND = AppError("PLAN_NOT_FOUND", "Plan not found.", 404)
    STEP_NOT_FOUND = AppError("STEP_NOT_FOUND", "Step not found.", 404)
    PLAN_NOT_FULLY_DECIDED = AppError(
        "PLAN_NOT_FULLY_DECIDED", "Decide every step before approving the plan.", 409
    )
    INVALID_DECISION = AppError(
        "INVALID_DECISION", "Decision must be accepted, edited or rejected.", 400
    )
    PLAN_NOT_DECIDABLE = AppError(
        "PLAN_NOT_DECIDABLE", "Only a proposed plan can be decided or approved.", 409
    )
