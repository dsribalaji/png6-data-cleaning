"""Main FastAPI application entry point.

Project: png6-data-cleaning
Team: TITAN (NCS26GA-46)
CodeStorm 2K26

Core loop, exact order:
ingest -> profile -> infer -> plan -> approve -> execute -> verify -> rollback
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.profile import router as profile_router
from app.api.plans import router as plans_router
from app.api.execute import router as execute_router
from app.api.tests import router as tests_router
from app.api.audit import router as audit_router
from app.core.events import router as events_router

# Core loop order: ingest -> profile -> infer -> plan -> approve -> execute -> verify -> rollback
app = FastAPI(
    title="PNG6 Agentic Data Cleaning Planner",
    version="0.1.0",
    description=(
        "Agentic Data Cleaning Planner backend. Core loop, exact order: "
        "ingest -> profile -> infer -> plan -> approve -> execute -> verify -> rollback."
    ),
)

# Permissive CORS for local dev: tighten before any public deployment (NFR-03)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from app.api (each router defines its own prefix)
app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(profile_router)
app.include_router(plans_router)
app.include_router(execute_router)
app.include_router(tests_router)
app.include_router(audit_router)

# Mount SSE router from app.core.events at /events
app.include_router(events_router, prefix="/events")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint.

    Returns operational status of the service.
    """
    return {"status": "ok", "service": "png6-api"}
