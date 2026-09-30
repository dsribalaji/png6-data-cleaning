"""Quarantine and cell security service.

STATUS: scaffold stub — not implemented.

FR-044 to FR-045:
- Isolates unparseable or severely malformed rows into quarantine while permitting
  the rest of the dataset ingestion and profiling to proceed uninterrupted.
- Detects and flags poisoned cells containing prompt-injection attempts or malicious
  payloads designed to compromise downstream LLM components.
"""

from typing import Any


def quarantine_row(
    dataset_id: str,
    row_index: int,
    raw: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Quarantine an unparseable or malicious row (FR-044, FR-045).

    TODO:
    - Save row payload and diagnostic reason to quarantine_records table
    - Flag any suspicious injection patterns (poisoned-cell flagging)
    - Allow parent ingestion job to continue without failing
    """
    raise NotImplementedError("quarantine not started")
