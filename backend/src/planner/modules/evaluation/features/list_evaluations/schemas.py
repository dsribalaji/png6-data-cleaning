"""Pydantic schemas for list_evaluations slice."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from planner.modules.evaluation.features.get_evaluation.schemas import EvaluationRunOut, _to_camel


class ListEvaluationsIn(BaseModel):
    """Input parameters for listing evaluation runs."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    page: int = 1
    page_size: int = 20


__all__ = ["EvaluationRunOut", "ListEvaluationsIn"]
