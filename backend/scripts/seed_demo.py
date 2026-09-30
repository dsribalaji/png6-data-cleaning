"""Seed a demo administrator for local showcase runs. Idempotent.

Usage (from backend/):
    PYTHONPATH=src DATABASE_URL="sqlite+aiosqlite:///./planner.db" \
        python scripts/seed_demo.py

Creates admin@example.com / Admin123! with the administrator role,
unless a user with that email already exists.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import select  # noqa: E402

from planner.core.db import SessionLocal  # noqa: E402
from planner.core.security import hash_password  # noqa: E402
from planner.modules.users.models import User, UserRole  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin123!"


async def main() -> None:
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"seed: {ADMIN_EMAIL} already exists, nothing to do")
            return
        user = User(
            email=ADMIN_EMAIL,
            first_name="Demo",
            last_name="Admin",
            password_hash=hash_password(ADMIN_PASSWORD),
            status="active",
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role="administrator"))
        await session.commit()
        print(f"seed: created {ADMIN_EMAIL} / {ADMIN_PASSWORD} (administrator)")


if __name__ == "__main__":
    asyncio.run(main())
