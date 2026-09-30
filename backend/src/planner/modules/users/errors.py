"""Static AppError instances for the users module (Backend.md).

Only user-domain codes live here; generic codes (NOT_FOUND, FORBIDDEN,
VALIDATION_ERROR, INTERNAL) come from planner.core.errors.
"""

from __future__ import annotations

from planner.core.errors import AppError, app_error


class UsersErrors:
    """Error catalogue instances for user authentication and management."""

    INVALID_CREDENTIALS: AppError = app_error("INVALID_CREDENTIALS")
    ACCOUNT_LOCKED: AppError = app_error("ACCOUNT_LOCKED")
    ACCOUNT_INACTIVE: AppError = app_error("ACCOUNT_INACTIVE")
    USER_EXISTS: AppError = app_error("USER_EXISTS")


__all__ = ["UsersErrors"]
