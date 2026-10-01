"""Application errors mapped to RFC 9457 application/problem+json (Backend.md)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ERROR_CATALOGUE: dict[str, tuple[int, str]] = {
    "INVALID_CREDENTIALS": (401, "Email or password is incorrect."),
    "ACCOUNT_LOCKED": (423, "Your account is locked. Try again in 15 minutes."),
    "ACCOUNT_INACTIVE": (403, "Your account is inactive. Contact an Administrator."),
    "USER_EXISTS": (409, "This user already exists."),
    "DATASET_NAME_TAKEN": (409, "A dataset with this name already exists."),
    "UNSUPPORTED_FILE_TYPE": (400, "Only .xlsx or .csv files can be uploaded."),
    "FILE_TOO_LARGE": (413, "The file is larger than {limit} MB."),
    "PLAN_NOT_FULLY_DECIDED": (409, "Decide every step before approving the plan."),
    "REASON_REQUIRED": (400, "Enter a reason of at least 10 characters."),
    "EXPORT_BLOCKED_TESTS_FAILED": (409, "Export is blocked because 1 or more tests failed."),
    "MODEL_CONNECTION_FAILED": (422, "Could not reach the provider. Check the key and endpoint."),
    "JOB_ALREADY_RUNNING": (409, "A job of this type is already running for this item."),
    "NOT_FOUND": (404, "The requested resource was not found."),
    "FORBIDDEN": (403, "You don't have access to this page."),
    "VALIDATION_ERROR": (422, "Request validation failed."),
    "SSO_REQUIRED": (403, "Sign in with single sign-on."),
    "RATE_LIMITED": (429, "Too many requests. Wait a minute and try again."),
    "INTERNAL": (500, "An unexpected error occurred."),
}


class AppError(Exception):
    """Business-rule failure mapped to RFC 9457 problem+json (Backend.md)."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        status: int | None = None,
        errors: list[str] | None = None,
    ) -> None:
        if code in ERROR_CATALOGUE:
            default_status, default_message = ERROR_CATALOGUE[code]
            if status is None:
                status = default_status
            if message is None:
                message = default_message
        else:
            if status is None:
                status = 400
            if message is None:
                message = code

        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.errors = errors


def app_error(code: str, **fmt: Any) -> AppError:
    """Look up an error in the catalogue and optionally format its message."""
    if code in ERROR_CATALOGUE:
        status, msg_tmpl = ERROR_CATALOGUE[code]
        msg = msg_tmpl.format(**fmt) if fmt else msg_tmpl
        return AppError(code=code, message=msg, status=status)
    return AppError(code=code, message=code, status=400)


def problem_response(
    status: int,
    title: str,
    detail: str,
    code: str,
    errors: list[str] | None = None,
) -> JSONResponse:
    """Create an RFC 9457 application/problem+json response."""
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(
        status_code=status,
        content=content,
        media_type="application/problem+json",
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Global handler for AppError instances."""
    return problem_response(
        status=exc.status,
        title=exc.code,
        detail=exc.message,
        code=exc.code,
        errors=exc.errors,
    )


async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Global handler for FastAPI RequestValidationError."""
    errors = [
        f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', '')}"
        for err in exc.errors()
    ]
    return problem_response(
        status=422,
        title="VALIDATION_ERROR",
        detail="Request validation failed.",
        code="VALIDATION_ERROR",
        errors=errors,
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global handler for unhandled exceptions (never leak internals)."""
    return problem_response(
        status=500,
        title="INTERNAL",
        detail="An unexpected error occurred.",
        code="INTERNAL",
    )
