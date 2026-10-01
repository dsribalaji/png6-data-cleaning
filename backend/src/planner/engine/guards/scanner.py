from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import polars as pl

# FR-045: text aimed at an LLM rather than being data. One case-insensitive regex,
# usable by Python `re` and by Polars (Rust regex) for whole-column scans.
INJECTION_PATTERNS: list[str] = [
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|prompts?|rules)\b",
    r"<\|?\s*(system|im_start|im_end|assistant)\s*\|?>",
    r"(^|\n)\s*(system|assistant)\s*:",
    r"\byou are now\b",
    r"\b(reveal|print|show)\b.{0,30}\b(system prompt|secrets?|api keys?)\b",
    r"\bdo not follow\b",
    r"\bas an ai\b",
    r"\bdrop\s+table\b",
    r"<script",
    r"```",
]
INJECTION_REGEX = "(?is)" + "|".join(f"(?:{p})" for p in INJECTION_PATTERNS)
_COMPILED = re.compile(INJECTION_REGEX)

# Zero-width joiners/spaces, bidi overrides and the BOM: invisible in a spreadsheet
# yet enough to split a keyword apart so a literal substring scan misses it.
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")


def normalise_for_scan(value: str) -> str:
    """Fold away the tricks that hide an instruction from a literal scan.

    Removes zero-width and bidi control characters, then applies Unicode NFKC so
    full-width and mathematical letters become plain ASCII. Without this the same
    instruction can be written in a form no regex on the raw text will match
    (FR-045). The caller still matches against the ORIGINAL value, so the flag
    keeps the real text for display.
    """
    stripped = _ZERO_WIDTH.sub("", value)
    stripped = "".join(c for c in stripped if unicodedata.category(c) != "Cf")
    return unicodedata.normalize("NFKC", stripped)


@dataclass
class InjectionFlag:
    column: str
    row: int
    value_preview: str
    reason: str


def scan_prompt_injection(cells: list[tuple[str, int, str]]) -> list[InjectionFlag]:
    """Scan cells for instruction-like text (prompt injection).

    Each cell is a tuple of (column_name, row_index, value). Matching is case-insensitive.
    """
    flags: list[InjectionFlag] = []
    for col, row_idx, val in cells:
        if val is None:
            continue
        val_str = str(val)
        m = _COMPILED.search(normalise_for_scan(val_str))
        if m:
            flags.append(
                InjectionFlag(
                    column=col,
                    row=row_idx,
                    value_preview=val_str[:60],
                    reason=f"Looks like an instruction to an AI model: '{m.group(0)[:40].lower()}'",
                )
            )
    return flags


def scan_frame(df: pl.DataFrame, limit: int = 200) -> list[InjectionFlag]:
    """Scan every text column of a frame (vectorised; cheap on large tables)."""
    flags: list[InjectionFlag] = []
    for col in df.columns:
        if df.schema[col] != pl.Utf8:
            continue
        # The vectorised regex cannot normalise, so it is used as a cheap
        # prefilter on the RAW text; normalise_for_scan below makes the final
        # decision, which is what catches zero-width and full-width spellings.
        hits = (
            df.select(pl.col(col))
            .with_row_index("_row")
            .filter(
                pl.col(col).str.contains(INJECTION_REGEX)
                | pl.col(col).map_elements(
                    lambda v: bool(_COMPILED.search(normalise_for_scan(v)))
                    if isinstance(v, str)
                    else False,
                    return_dtype=pl.Boolean,
                )
            )
            .head(max(limit - len(flags), 0))
        )
        flags += scan_prompt_injection(
            [(col, int(r), v) for r, v in zip(hits["_row"], hits[col], strict=True)]
        )
        if len(flags) >= limit:
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
