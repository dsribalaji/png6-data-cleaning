from __future__ import annotations

from dataclasses import dataclass

import polars as pl

INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all instructions",
    "system:",
    "as an ai",
    "drop table",
    "<script",
    "```",
    "do not follow",
]


@dataclass
class InjectionFlag:
    column: str
    row: int
    value_preview: str
    reason: str


def scan_prompt_injection(cells: list[tuple[str, int, str]]) -> list[InjectionFlag]:
    """Scan cells for instruction-like substrings (prompt injection).

    Each cell is a tuple of (column_name, row_index, value).
    Matches are case-insensitive.
    """
    flags: list[InjectionFlag] = []
    for col, row_idx, val in cells:
        if val is None:
            continue
        val_str = str(val)
        val_lower = val_str.lower()
        for pat in INJECTION_PATTERNS:
            if pat in val_lower:
                flags.append(
                    InjectionFlag(
                        column=col,
                        row=row_idx,
                        value_preview=val_str[:60],
                        reason=f"Matched prompt injection pattern: '{pat}'",
                    )
                )
                break
    return flags


def check_sparsity(df: pl.DataFrame, threshold: float = 0.95) -> list[str]:
    """Return column names with null fraction >= threshold."""
    if len(df) == 0:
        return []
    total_rows = len(df)
    sparse_cols: list[str] = []
    for col in df.columns:
        null_count = df[col].null_count()
        if (null_count / total_rows) >= threshold:
            sparse_cols.append(col)
    return sparse_cols


def check_size_limits(n_bytes: int, max_mb: int = 50) -> None:
    """Raise ValueError if byte size exceeds max_mb megabytes."""
    limit_bytes = max_mb * 1024 * 1024
    if n_bytes > limit_bytes:
        raise ValueError(
            f"FILE_TOO_LARGE: file size {n_bytes} bytes exceeds {max_mb} MB limit "
            f"({limit_bytes} bytes)"
        )


def mask_sample(value: str, keep: int = 2) -> str:
    """Data minimisation for LLM samples: first `keep` chars + '***' if longer than keep+2."""
    if len(value) > keep + 2:
        return value[:keep] + "***"
    return value
