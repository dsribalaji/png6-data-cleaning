"""Celery tasks for the model_config module (Backend.md).

No Celery tasks are defined in this module. Model connection tests run inline
within the HTTP request as they are fast and bounded by short timeouts.
"""

from __future__ import annotations
