"""engine/nested.py: every nested cell is parsed or accounted for, never dropped silently."""

from __future__ import annotations

import pytest

from planner.engine.nested import parse_nested, summarise


@pytest.mark.parametrize(
    ("cell", "status", "items"),
    [
        ('[{"a": "1"}, {"a": "2"}]', "ok", [{"a": "1"}, {"a": "2"}]),
        ('{"a": 1}', "ok", [{"a": 1}]),
        ("[{'a': '1', 'ok': True, 'x': None}]", "repaired", [{"a": "1", "ok": True, "x": None}]),
        ('[{"a": "1"},{"a": "2"},{"a": "3', "partial", [{"a": "1"}, {"a": "2"}]),
        ('[{"a": "1"},{"a": "2"},{"', "partial", [{"a": "1"}, {"a": "2"}]),
        ("[{nonsense", "invalid", []),
        ("", "empty", []),
        ("plain text", "empty", []),
        (None, "empty", []),
    ],
)
def test_parse_nested__status_and_items(cell: object, status: str, items: list[dict]) -> None:
    parsed = parse_nested(cell)
    assert (parsed.status, parsed.items) == (status, items)


def test_parse_nested__nested_objects_flattened_lists_kept_as_text() -> None:
    parsed = parse_nested(
        '[{"sku": "1", "price": {"amount": "$2.00", "cur": "USD"}, "tags": [1, 2]}]'
    )
    assert parsed.items == [
        {"sku": "1", "price.amount": "$2.00", "price.cur": "USD", "tags": "[1, 2]"}
    ]


def test_parse_nested__never_evaluates_code() -> None:
    assert parse_nested("[__import__('os').system('echo hi')]").status == "invalid"


def test_summarise__counts_every_cell() -> None:
    counts = summarise(['[{"a": 1}]', "[{'a': 1}]", '[{"a": 1},{"a', "", "[x"])
    assert counts == {"ok": 1, "repaired": 1, "partial": 1, "invalid": 1, "empty": 1, "items": 3}
