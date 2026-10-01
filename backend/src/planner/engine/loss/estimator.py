"""Loss estimation functions for data operations.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from planner.engine.ops.base import OPS, LossEstimate

DEFAULT_LOSS_THRESHOLD: float = 0.05


def estimate_step_loss(
    df: pl.DataFrame, op_name: str, params: dict[str, Any]
) -> LossEstimate:
    """Estimate data loss for a single pipeline step.

    Raises ValueError on unknown operation.
    """
    try:
        op = OPS[op_name]
    except KeyError as exc:
        raise ValueError(f"Unknown operation: '{op_name}'") from exc

    return op.estimate_loss(df, params)


def cumulative_loss(losses: list[LossEstimate]) -> float:
    """Compute cumulative loss across a sequence of operations.

    Formula: 1 - prod(1 - l.estimated_loss), bounded in [0.0, 1.0].
    """
    if not losses:
        return 0.0

    prod = math.prod(1.0 - max(0.0, min(1.0, float(l.estimated_loss))) for l in losses)
    cum = 1.0 - prod
    return max(0.0, min(1.0, float(cum)))


def check_threshold(
    cum_loss: float, threshold: float = DEFAULT_LOSS_THRESHOLD
) -> bool:
    """Check if cumulative loss is within the allowed threshold."""
    return cum_loss <= threshold
