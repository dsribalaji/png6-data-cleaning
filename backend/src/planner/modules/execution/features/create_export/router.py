"""Router for create_export feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.execution.features.create_export.service import create_export
from planner.modules.execution.schemas import ExportRequest, ExportResponse

router = APIRouter(prefix="/api/v1/plans", tags=["execution"])


def _engineer_only() -> None:
    """placeholder for require_roles(...) until the users module lands (W1).

    Note: viewers are also allowed to export per spec, but roles aren't wired yet.
    """


@router.post("/{plan_id}/exports", response_model=ExportResponse)
async def export_plan_dataset(
    plan_id: UUID,
    req: ExportRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_engineer_only),
) -> ExportResponse:
    """Create an export download URL for the plan's executed dataset."""
    return await create_export(session, plan_id, req, actor_id=None)
