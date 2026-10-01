"""Seed a demo administrator for local showcase runs. Idempotent.

Usage (from backend/):
    PYTHONPATH=src DATABASE_URL="sqlite+aiosqlite:///./planner.db" \
        python scripts/seed_demo.py

Creates admin@example.com / Admin123456! (administrator) and
engineer@example.com / Engineer123! (data_engineer), skipping any that exist.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import select

from planner.core.db import SessionLocal
from planner.core.security import hash_password
from planner.modules.users.models import User, UserRole

# (email, password, first name, role). Local demo only; change or remove for any shared deployment.
DEMO_USERS = (
    ("admin@example.com", "Admin123456!", "Admin", "administrator"),
    # The cleaning flow (upload, decide, approve, export, rollback) is Data Engineer work (PRD §2).
    ("engineer@example.com", "Engineer123!", "Engineer", "data_engineer"),
)


async def main() -> None:
    async with SessionLocal() as session:
        for email, password, first_name, role in DEMO_USERS:
            existing = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"seed: {email} already exists, nothing to do")
                continue
            user = User(
                email=email,
                first_name=first_name,
                last_name="Demo",
                password_hash=hash_password(password),
                status="active",
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role=role))
            print(f"seed: created {email} / {password} ({role})")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
