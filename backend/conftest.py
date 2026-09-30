"""Isolate every test run: throwaway SQLite DB + local storage, eager Celery.

Runs before any ``planner`` import (settings and the engine read env at import time),
so tests never touch a developer's ./planner.db or ./storage.
"""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="planner-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_ROOT"] = f"{_tmp}/storage"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

# Register every model on Base.metadata (same list as migrations/env.py) so slice
# tests' create_all() builds complete schemas: cross-module FKs and audit rows.
import planner.modules.users.models  # noqa: E402,F401
import planner.modules.datasets.models  # noqa: E402,F401
import planner.modules.profiling.models  # noqa: E402,F401
import planner.modules.planning.models  # noqa: E402,F401
import planner.modules.execution.models  # noqa: E402,F401
import planner.modules.validation.models  # noqa: E402,F401
import planner.modules.model_config.models  # noqa: E402,F401
import planner.modules.audit.models  # noqa: E402,F401
import planner.modules.evaluation.models  # noqa: E402,F401
