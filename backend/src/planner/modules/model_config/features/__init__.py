"""Model config features package."""

from __future__ import annotations

from fastapi import APIRouter

from planner.modules.model_config.features.get_model_config.router import (
    router as get_model_config_router,
)
from planner.modules.model_config.features.list_providers.router import (
    router as list_providers_router,
)
from planner.modules.model_config.features.test_model_connection.router import (
    router as test_model_connection_router,
)
from planner.modules.model_config.features.update_model_config.router import (
    router as update_model_config_router,
)

router = APIRouter()
router.include_router(get_model_config_router)
router.include_router(update_model_config_router)
router.include_router(test_model_connection_router)
router.include_router(list_providers_router)

__all__ = [
    "get_model_config_router",
    "list_providers_router",
    "router",
    "test_model_connection_router",
    "update_model_config_router",
]
