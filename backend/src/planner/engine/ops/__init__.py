"""Operation abstractions, registry, and inverse applications.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

from planner.engine.ops.base import (
    OPS,
    InverseOp,
    LossEstimate,
    Operation,
    apply_inverse,
    frame_equal,
)

__all__ = [
    "OPS",
    "InverseOp",
    "LossEstimate",
    "Operation",
    "apply_inverse",
    "frame_equal",
]
