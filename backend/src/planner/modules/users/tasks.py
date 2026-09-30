"""Celery tasks for the users module (Backend.md).

NOTE: The users module requires no background Celery tasks. All authentication,
session rotation, user lifecycle management, and invitation flows are synchronous
REST operations executed within the FastAPI request lifecycle.
"""

from __future__ import annotations
