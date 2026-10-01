"""Service logic for user logout (Backend.md)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.security import RequestPrincipal, hash_token
from planner.modules.users.features.logout.schemas import LogoutResponse
from planner.modules.users.models import RefreshToken


async def logout_user(
    session: AsyncSession,
    actor: RequestPrincipal,
    refresh_token_raw: str | None = None,
) -> LogoutResponse:
    """Revoke presented refresh token if present and return success envelope."""
    if refresh_token_raw:
        token_h = hash_token(refresh_token_raw)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_h)
        result = await session.execute(stmt)
        token_row = result.scalar_one_or_none()

        if token_row is not None and token_row.revoked_at is None:
            token_row.revoked_at = datetime.now(UTC)
            await session.commit()

    return LogoutResponse(message="Logged out successfully")
