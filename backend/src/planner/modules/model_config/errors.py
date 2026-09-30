"""Static AppError instances for the model_config module (Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError

MODEL_CONFIG_NOT_FOUND = AppError(
    "MODEL_CONFIG_NOT_FOUND",
    "No model configuration saved yet.",
    404,
)

MODEL_CONNECTION_FAILED = AppError(
    "MODEL_CONNECTION_FAILED",
    "Could not reach the provider. Check the key and endpoint.",
    422,
)

CONFIGURATION_ERROR = AppError(
    "CONFIGURATION_ERROR",
    "Model credential encryption is not configured (FERNET_KEY).",
    500,
)
