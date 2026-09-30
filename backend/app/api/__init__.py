"""API routers package."""

from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.profile import router as profile_router
from app.api.plans import router as plans_router
from app.api.execute import router as execute_router
from app.api.tests import router as tests_router
from app.api.audit import router as audit_router

__all__ = [
    "auth_router",
    "datasets_router",
    "profile_router",
    "plans_router",
    "execute_router",
    "tests_router",
    "audit_router",
]
