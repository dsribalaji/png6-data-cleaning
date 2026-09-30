"""Static AppError instances for the evaluation module (Backend.md)."""

from __future__ import annotations

from planner.core.errors import AppError

EVALUATION_NOT_FOUND = AppError("EVALUATION_NOT_FOUND", "Evaluation run not found.", 404)
BENCHMARK_SET_NOT_FOUND = AppError("BENCHMARK_SET_NOT_FOUND", "Benchmark set not found.", 404)

__all__ = ["BENCHMARK_SET_NOT_FOUND", "EVALUATION_NOT_FOUND"]
