"""One parser for nested records stored in a cell (JSON-like text), used by profiling,
rule inference, the expand_nested operation and reconciliation, so they always agree.

Real exports are messy. In one 30k-row test file 4% of cells were not strict
JSON: Python-style single quotes ({'a': '1'}), and lists cut off mid-item. A strict
parser dropped all of them silently. Here every cell gets a status instead:

- ok        strict JSON
- repaired  not JSON but a valid Python literal (single quotes, True/None); parsed
            with ast.literal_eval, which evaluates literals only, never code
- partial   cut off; the complete items before the cut are kept, the rest is lost
- invalid   looks nested but nothing could be recovered
- empty     blank cell, or text that is not nested data at all
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["ok", "repaired", "partial", "invalid", "empty"]

MAX_CELL_CHARS = 1_000_000  # literal_eval on huge text is slow; such cells are invalid
_DECODER = json.JSONDecoder()


@dataclass
class ParsedCell:
    items: list[dict[str, Any]] = field(default_factory=list)
    status: Status = "empty"


def looks_nested(cell: Any) -> bool:
    return isinstance(cell, str) and cell.lstrip()[:1] in ("[", "{")


def parse_nested(cell: Any) -> ParsedCell:
    """Parse one cell into a list of flat records, with how it was recovered."""
    if not looks_nested(cell):
        return ParsedCell()
    text = cell.strip()
    try:
        return ParsedCell(_records(json.loads(text)), "ok")
    except ValueError:
        pass
    if len(text) <= MAX_CELL_CHARS:
        try:
            value = ast.literal_eval(text)
            if isinstance(value, (list, dict)):
                return ParsedCell(_records(value), "repaired")
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            pass
    salvaged = _salvage(text)
    return ParsedCell(salvaged, "partial") if salvaged else ParsedCell(status="invalid")


def _salvage(text: str) -> list[dict[str, Any]]:
    """Complete objects at the start of a cut-off list: '[{..},{..},{"a":' -> 2 items."""
    if not text.startswith("["):
        return []
    items: list[dict[str, Any]] = []
    pos = 1
    while pos < len(text):
        while pos < len(text) and text[pos] in " \t\r\n,":
            pos += 1
        try:
            value, pos = _DECODER.raw_decode(text, pos)
        except ValueError:
            break
        if isinstance(value, dict):
            items.append(value)
    return [_flatten(i) for i in items]


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [_flatten(value)]
    if isinstance(value, list):
        return [_flatten(v) for v in value if isinstance(v, dict)]
    return []


def _flatten(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """{"a": {"b": 1}, "tags": [1, 2]} -> {"a.b": 1, "tags": "[1, 2]"}: one column per
    leaf value; lists inside a record stay as JSON text (a further level of nesting)."""
    flat: dict[str, Any] = {}
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{name}."))
        elif isinstance(value, list):
            flat[name] = json.dumps(value, default=str)
        else:
            flat[name] = value
    return flat


def summarise(cells: list[Any]) -> dict[str, int]:
    """Counts per status plus recovered items: the expand step's rationale."""
    counts = {"ok": 0, "repaired": 0, "partial": 0, "invalid": 0, "empty": 0, "items": 0}
    for cell in cells:
        parsed = parse_nested(cell)
        counts[parsed.status] += 1
        counts["items"] += len(parsed.items)
    return counts
