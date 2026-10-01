"""Evaluation harness: labelled benchmark corpus plus the scorer (C1, C2).

Pure data logic. Nothing here imports FastAPI, SQLAlchemy or the network, so the
scorer can be run in CI with the model switched off and stay deterministic.
"""

from __future__ import annotations

from planner.engine.evaluation.corpus import BenchmarkCase, all_cases
from planner.engine.evaluation.scorer import (
    BAR,
    CaseResult,
    bar_report,
    check_bar,
    run_benchmark,
    run_case,
    score_suite,
)

__all__ = [
    "BAR",
    "BenchmarkCase",
    "CaseResult",
    "all_cases",
    "bar_report",
    "check_bar",
    "run_benchmark",
    "run_case",
    "score_suite",
]

