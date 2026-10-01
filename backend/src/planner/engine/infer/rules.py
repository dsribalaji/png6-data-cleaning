from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from planner.engine.nested import parse_nested
import rapidfuzz.fuzz
import rapidfuzz.process

from planner.engine.profile.profiler import TableProfile


@dataclass
class InferredRule:
    rule_type: str
    columns: list[str]
    expression: dict[str, Any]
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    source: str = "deterministic"


def _cluster_entity_groups(
    values: list[str],
    # 60.0 verified on the golden fixture: merges "Hart Business Solutions"+", LLC" (90.2)
    # and "Microsoft Corporation"+"Microsoft Corporation (India) Private Limited" (63.6)
    # while rejecting code-like pairs ("PO-1141" vs "PO-1424", VATs, boilerplate addresses).
    cutoff: float = 60.0,
) -> tuple[list[dict[str, Any]], int]:
    def _extension_scorer(a: str, b: str, *, score_cutoff: float = 0.0, **kwargs: object) -> float:
        """token_sort_ratio gated on suffix-extension.

        Merges only when the shorter name is a word-boundary prefix of the longer
        ("Hart Business Solutions" -> "Hart Business Solutions, LLC",
        "Microsoft Corporation" -> "Microsoft Corporation (India) Private Limited")
        while rejecting code-like pairs that merely share characters
        ("PO-1141" vs "PO-1424", "P4460R1ZL" vs "P7945R1ZL", boilerplate addresses).
        """
        base = rapidfuzz.fuzz.token_sort_ratio(a, b)
        if base < cutoff:
            return 0.0
        short, long = (a, b) if len(a) <= len(b) else (b, a)
        if long.startswith(short):
            if len(long) == len(short):
                return base  # identical strings (case/whitespace variants)
            if long[len(short)] in " ,(-":
                return base
        return 0.0

    counts = Counter(values)
    distinct_vals = list(counts.keys())
    # Sort distinct values by count descending, then by length
    sorted_distinct = sorted(distinct_vals, key=lambda v: (-counts[v], len(str(v))))

    used: set[str] = set()
    groups: list[dict[str, Any]] = []
    groups_with_variants = 0

    lower_to_orig: dict[str, list[str]] = {}
    for v in sorted_distinct:
        k = str(v).strip().lower()
        lower_to_orig.setdefault(k, []).append(v)

    remaining_lowers = list(lower_to_orig.keys())

    for val in sorted_distinct:
        if val in used:
            continue
        target_lower = str(val).strip().lower()
        if target_lower not in remaining_lowers:
            continue

        matches = rapidfuzz.process.extract(
            target_lower,
            remaining_lowers,
            scorer=_extension_scorer,
            score_cutoff=cutoff,
        )

        matched_variants: list[str] = []
        for match_str, _score, _idx in matches:
            for orig in lower_to_orig.get(match_str, []):
                if orig not in used:
                    matched_variants.append(orig)

        # Canonical is the most frequent variant stripped
        matched_variants.sort(key=lambda x: (-counts[x], len(str(x)), str(x)))
        canonical = str(matched_variants[0]).strip()

        group = {
            "canonical": canonical,
            "variants": matched_variants,
        }
        groups.append(group)
        if len(matched_variants) > 1:
            groups_with_variants += 1

        for m in matched_variants:
            used.add(m)
            m_lower = str(m).strip().lower()
            if m_lower in remaining_lowers:
                remaining_lowers.remove(m_lower)

    return groups, groups_with_variants


def infer_rules(df: pl.DataFrame, profile: TableProfile) -> list[InferredRule]:
    rules: list[InferredRule] = []
    row_count = profile.row_count

    # 0. All-null columns -> drop_column (deterministic; confidence 1.0)
    for col in profile.columns:
        if row_count > 0 and col.null_pct >= 1.0:
            rules.append(
                InferredRule(
                    rule_type="all_null",
                    columns=[col.name],
                    expression={"column": col.name},
                    confidence=1.0,
                    evidence={"null_pct": col.null_pct, "row_count": row_count},
                    source="deterministic",
                )
            )

    # 1. Primary key
    primary_key_col: str | None = None
    for col in profile.columns:
        if (
            col.semantic_type == "identifier"
            and col.null_pct == 0.0
            and col.distinct_count == row_count
            and row_count > 0
        ):
            primary_key_col = col.name
            rules.append(
                InferredRule(
                    rule_type="primary_key",
                    columns=[col.name],
                    expression={"column": col.name},
                    confidence=1.0,
                    evidence={"distinct_count": col.distinct_count, "row_count": row_count},
                    source="deterministic",
                )
            )
            break

    # 2. Entity groups
    for col in profile.columns:
        if col.semantic_type in ("category", "free_text") and 2 <= col.distinct_count <= 50:
            raw_vals = [str(v) for v in df[col.name].drop_nulls().to_list()]
            if not raw_vals:
                continue
            groups, groups_with_variants = _cluster_entity_groups(raw_vals, cutoff=60.0)
            if groups_with_variants > 0:
                confidence = round(1.0 - (groups_with_variants / col.distinct_count), 4)
                rules.append(
                    InferredRule(
                        rule_type="entity_group",
                        columns=[col.name],
                        expression={"column": col.name, "groups": groups},
                        confidence=confidence,
                        evidence={
                            "distinct_count": col.distinct_count,
                            "groups_with_variants": groups_with_variants,
                            "total_variants": sum(len(g["variants"]) for g in groups),
                        },
                        source="deterministic",
                    )
                )

    # 3. Arithmetic relationships
    numeric_cols = [c.name for c in profile.columns if df[c.name].dtype.is_numeric()]
    pairs_tested = 0
    max_pairs = 40

    # Test equality pairs
    equality_found_pairs: set[tuple[str, str]] = set()
    for a, b in itertools.combinations(numeric_cols, 2):
        if pairs_tested >= max_pairs:
            break
        pairs_tested += 1

        sub = df.select([a, b]).drop_nulls()
        n_rows = len(sub)
        if n_rows == 0:
            continue

        diff = (sub[a] - sub[b]).abs()
        matches = int((diff <= 1e-6).sum())
        ratio = matches / n_rows

        if ratio >= 0.95:
            # Deterministically choose target vs formula
            target, formula = (a, b) if a.lower() > b.lower() else (b, a)
            if "total" in target.lower() and "total" not in formula.lower():
                pass
            elif "total" in formula.lower() and "total" not in target.lower():
                target, formula = formula, target

            equality_found_pairs.add((target, formula))
            rules.append(
                InferredRule(
                    rule_type="arithmetic",
                    columns=[target, formula],
                    expression={"target": target, "formula": formula, "kind": "equality"},
                    confidence=round(ratio, 4),
                    evidence={"matching_rows": matches, "total_rows": n_rows, "tolerance": 1e-6},
                    source="deterministic",
                )
            )

    # Test sum triples: a == b + c
    if len(numeric_cols) >= 3 and pairs_tested < max_pairs:
        for a in numeric_cols:
            other_cols = [c for c in numeric_cols if c != a]
            for b, c in itertools.combinations(other_cols, 2):
                if pairs_tested >= max_pairs:
                    break
                pairs_tested += 1

                sub = df.select([a, b, c]).drop_nulls()
                n_rows = len(sub)
                if n_rows == 0:
                    continue

                diff = (sub[a] - (sub[b] + sub[c])).abs()
                matches = int((diff <= 1e-6).sum())
                ratio = matches / n_rows

                if ratio >= 0.95:
                    rules.append(
                        InferredRule(
                            rule_type="arithmetic",
                            columns=[a, b, c],
                            expression={"target": a, "formula": f"{b} + {c}", "kind": "sum"},
                            confidence=round(ratio, 4),
                            evidence={
                                "matching_rows": matches,
                                "total_rows": n_rows,
                                "tolerance": 1e-6,
                            },
                            source="deterministic",
                        )
                    )

    # 4. One to many (nested JSON)
    for col in profile.columns:
        if col.semantic_type == "nested_json":
            parent_key = primary_key_col if primary_key_col is not None else "_row"
            parts = col.name.split("_")
            child_table = "".join(p.capitalize() for p in parts)

            total_items = 0
            sample_keys_set: set[str] = set()

            for cell in df[col.name].drop_nulls().to_list():
                if not isinstance(cell, str):
                    continue
                items = parse_nested(cell).items
                total_items += len(items)
                for item in items:
                    sample_keys_set.update(item.keys())

            rules.append(
                InferredRule(
                    rule_type="one_to_many",
                    columns=[col.name],
                    expression={
                        "parent_key": parent_key,
                        "child_table": child_table,
                        "item_count": total_items,
                    },
                    confidence=1.0,
                    evidence={"sample_item_keys": sorted(sample_keys_set)},
                    source="deterministic",
                )
            )

    # 5. Semantic types
    for col in profile.columns:
        if col.semantic_type not in ("unknown", "free_text"):
            rules.append(
                InferredRule(
                    rule_type="semantic_type",
                    columns=[col.name],
                    expression={"column": col.name, "semantic_type": col.semantic_type},
                    confidence=0.9,
                    evidence={"physical_type": col.physical_type},
                    source="deterministic",
                )
            )

    # 6. Cross-field fill
    for col in profile.columns:
        if col.null_count > 0 and col.null_count < row_count:
            null_mask = df[col.name].is_null()
            null_cnt = int(null_mask.sum())
            if null_cnt >= 2:
                for other in profile.columns:
                    if other.name == col.name:
                        continue
                    null_slice = df.filter(null_mask)[other.name].drop_nulls()
                    not_null_slice = df.filter(~null_mask)[other.name].drop_nulls()

                    if len(null_slice) == null_cnt and null_slice.n_unique() == 1:
                        if not_null_slice.n_unique() > 1:
                            const_val = null_slice[0]
                            rules.append(
                                InferredRule(
                                    rule_type="cross_field_fill",
                                    columns=[col.name, other.name],
                                    expression={
                                        "target": col.name,
                                        "source": other.name,
                                        "value": const_val,
                                    },
                                    confidence=0.85,
                                    evidence={"null_rows_matched": null_cnt},
                                    source="deterministic",
                                )
                            )

    return rules
