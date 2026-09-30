"""Static AppError instances for the audit module (Backend.md).

This module requires no module-specific business error codes beyond
the authentication and authorization errors handled by require_roles
(e.g., FORBIDDEN, INVALID_CREDENTIALS in planner.core.errors).
"""

from __future__ import annotations

from planner.core.errors import AppError

__all__ = ["AppError"]
