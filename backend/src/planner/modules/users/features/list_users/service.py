"""Service logic for the list_users use case (Backend.md)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.pagination import Page, build_page
from planner.core.security import RequestPrincipal
from planner.modules.users.features.me.schemas import UserRead
from planner.modules.users.models import User, UserRole


async def list_users_service(
    page: int,
    page_size: int,
    session: AsyncSession,
    actor: RequestPrincipal,
) -> Page[UserRead]:
    """Return a paginated user directory with each user's single role joined in.

    Ordered oldest first, with email as a stable tiebreak so pagination is
    deterministic when rows share a creation timestamp.
    """
    total = (
        await session.execute(select(func.count()).select_from(User))
    ).scalar_one()

    stmt = (
        select(User, UserRole.role)
        .outerjoin(UserRole, UserRole.user_id == User.id)
        .order_by(User.created_at.asc(), User.email.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).all()

    items = [
        UserRead(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            status=user.status,
            role=role,
        )
        for user, role in rows
    ]
    return build_page(items=items, total=total, page=page, page_size=page_size)
