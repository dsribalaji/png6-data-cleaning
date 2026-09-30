"""HTTP router for the list_users use case (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.pagination import Page, page_params
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.users.features.list_users.schemas import UserRead
from planner.modules.users.features.list_users.service import list_users_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
async def list_users_endpoint(
    page_and_size: tuple[int, int] = Depends(page_params),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("administrator")),
) -> Page[UserRead]:
    """List users with pagination (administrator only)."""
    page, page_size = page_and_size
    return await list_users_service(
        page=page,
        page_size=page_size,
        session=session,
        actor=principal,
    )
