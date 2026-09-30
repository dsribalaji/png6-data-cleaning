"""Data loss estimation service.

STATUS: scaffold stub — not implemented.

FR-028 to FR-031: Estimates rows, columns, and cells affected before step execution.
Calculates step loss % and tracks cumulative plan loss %.
PROPOSED (contract §6, P3): Automatically holds step for manual approval if
loss_pct exceeds settings.loss_threshold_pct (5.0%).
"""

from typing import Any


def estimate_step(step: dict[str, Any]) -> dict[str, Any]:
    """Estimate impact and data loss percentage for a proposed plan step before execution (FR-028).

    TODO:
    - Count rows_affected, cols_affected, cells_affected
    - Calculate loss_pct relative to current active dataset state
    - Flag held_for_approval = True if loss_pct > settings.loss_threshold_pct (PROPOSED 5%)
    - Accumulate into cumulative plan loss (FR-030)
    """
    raise NotImplementedError("loss estimator not started")
