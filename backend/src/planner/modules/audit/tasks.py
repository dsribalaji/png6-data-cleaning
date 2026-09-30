"""Celery tasks for the audit module.

There are no asynchronous Celery tasks for the audit module.
Audit writes happen synchronously inline within each request or task's database
transaction (Backend.md: "in the caller's transaction") to guarantee strong
consistency and audit integrity.
"""

from __future__ import annotations

__all__: list[str] = []
