"""Evaluation vertical slices."""

from __future__ import annotations

from fastapi import APIRouter

from planner.modules.evaluation.features.create_evaluation.router import router as create_router
from planner.modules.evaluation.features.get_evaluation.router import router as get_router
from planner.modules.evaluation.features.list_evaluations.router import router as list_router

router = APIRouter()
router.include_router(create_router)
router.include_router(list_router)
router.include_router(get_router)

__all__ = ["create_router", "get_router", "list_router", "router"]
