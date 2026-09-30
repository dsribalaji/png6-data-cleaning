"""Celery app, queues, routing and beat schedule (Backend.md).

One image starts as API, worker or scheduler. In local demo mode
(``CELERY_TASK_ALWAYS_EAGER=true``) tasks run inline and the result backend is
in-memory, so no broker or Redis is required (contract 10.5).
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from celery import Celery
from kombu import Queue

from planner.core.config import settings

logger = logging.getLogger(__name__)

QUEUES: tuple[Queue, ...] = (
    Queue("ingest"),
    Queue("profile"),
    Queue("plan"),
    Queue("execute"),
    Queue("validate"),
    Queue("eval"),
)

# task_routes maps a task name prefix to its queue. Explicit task names are listed
# first; the ``...tasks.*`` patterns cover the other modules' task modules.
TASK_ROUTES: dict[str, str] = {
    "planner.modules.datasets.tasks.ingest_dataset": "ingest",
    "planner.modules.datasets.tasks.poll_n8n_folder": "ingest",
    "planner.core.outbox.relay_outbox": "celery",
    "planner.modules.profiling.tasks.*": "profile",
    "planner.modules.planning.tasks.*": "plan",
    "planner.modules.execution.tasks.*": "execute",
    "planner.modules.validation.tasks.*": "validate",
    "planner.modules.evaluation.tasks.*": "eval",
}

EAGER = settings.celery_task_always_eager
RESULT_BACKEND = "cache+memory://" if EAGER else settings.redis_url

celery_app = Celery("planner", broker=settings.celery_broker_url, backend=RESULT_BACKEND)

celery_app.conf.update(
    task_queues=QUEUES,
    task_routes=TASK_ROUTES,
    # Retries: exponential backoff, max 3, then the dead-letter queue + job.failed.
    # Configured per task via autoretry_for / retry_backoff (Backend.md).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=10,
    task_always_eager=EAGER,
    task_eager_propagates=True,
    # LLM tasks: soft_time_limit=120. Execute tasks: soft_time_limit=900.
)

celery_app.conf.beat_schedule = {
    "poll-n8n-folder": {
        "task": "planner.modules.datasets.tasks.poll_n8n_folder",
        "schedule": settings.n8n_folder_poll_minutes * 60,
    },
    "outbox-relay": {
        "task": "planner.core.outbox.relay_outbox",
        "schedule": 30.0,
    },
}


def register_all_tasks(app: Celery) -> None:
    """Register every available task module on ``app``.

    Imports are guarded: a module that fails to import (not yet written by its
    slice, or a missing optional dependency) is logged and skipped so the worker
    always starts.
    """
    try:
        from planner.core import outbox

        register = getattr(outbox, "register_tasks", None)
        if callable(register):
            register(app)
        else:
            app.tasks.register(outbox.relay_outbox)
    except Exception as exc:  # noqa: BLE001 - worker must start regardless
        logger.warning("could not register outbox tasks: %s", exc)

    try:
        from planner.modules.datasets import tasks as dataset_tasks

        register = getattr(dataset_tasks, "register_tasks", None)
        if callable(register):
            register(app)
        else:
            app.autodiscover_tasks(["planner.modules.datasets.tasks"])
    except Exception as exc:  # noqa: BLE001 - worker must start regardless
        logger.warning("could not register datasets tasks: %s", exc)

    # Integration 2026-09-30: the remaining modules' tasks.py files register
    # themselves via @celery_app.task on import, so importing them here makes
    # the full upload -> profile -> infer -> plan -> execute chain work in
    # both eager (demo) and worker (production) modes.
    for _module in ("profiling", "planning", "execution", "validation", "evaluation"):
        try:
            importlib.import_module(f"planner.modules.{_module}.tasks")
        except Exception as exc:  # noqa: BLE001 - worker must start regardless
            logger.warning("could not register %s tasks: %s", _module, exc)


def task_names() -> list[str]:
    """Return the sorted task names currently registered (diagnostics/tests)."""
    return sorted(celery_app.tasks)


def send_task_eager_aware(
    name: str,
    *,
    args: list | None = None,
    kwargs: dict | None = None,
    queue: str | None = None,
) -> None:
    """Publish a task honouring ``task_always_eager``.

    Integration 2026-09-30: Celery's ``task_always_eager`` has NO effect on
    ``send_task()`` — it only applies to ``apply_async()``/``delay()``. This
    helper resolves the registered task and uses ``apply_async`` so eager
    (demo) mode genuinely runs inline while production still publishes to
    the broker.
    """
    task = celery_app.tasks[name]
    # Nested-eager guard (integration 2026-09-30): when a task running under
    # asyncio.run() chains another eager task, the inner task's own
    # asyncio.run() would raise "cannot be called from a running event loop".
    # Offload to a fresh thread so the inner task gets a clean loop.
    if celery_app.conf.task_always_eager:
        import asyncio as _asyncio_mod
        import concurrent.futures as _futures

        try:
            _asyncio_mod.get_running_loop()
        except RuntimeError:
            pass
        else:
            with _futures.ThreadPoolExecutor(max_workers=1) as _pool:
                return _pool.submit(
                    lambda: task.apply_async(
                        args=args or [], kwargs=kwargs or {}, queue=queue
                    )
                ).result()
    task.apply_async(args=args or [], kwargs=kwargs or {}, queue=queue)


async def dispatch_task(
    name: str,
    *,
    args: list | None = None,
    kwargs: dict | None = None,
    queue: str | None = None,
) -> None:
    """Send a Celery task from async API code.

    Integration 2026-09-30: eager tasks execute inline via ``asyncio.run()``,
    which raises inside the API's running event loop. Running ``send_task``
    in a worker thread avoids that in eager (demo) mode, and keeps broker
    publishing off the event loop in production mode.
    """
    import asyncio as _asyncio

    def _send() -> None:
        # Eager-aware: task_always_eager is ignored by send_task().
        send_task_eager_aware(name, args=args, kwargs=kwargs, queue=queue)

    await _asyncio.to_thread(_send)


def describe() -> dict[str, Any]:
    """Return a summary of the worker configuration (diagnostics/tests)."""
    return {
        "broker": settings.celery_broker_url,
        "result_backend": RESULT_BACKEND,
        "queues": sorted(q.name for q in QUEUES),
        "routes": dict(TASK_ROUTES),
        "beat_schedule": dict(celery_app.conf.beat_schedule),
        "task_always_eager": EAGER,
    }


# NOTE: registration runs last so that task modules importing
# {celery_app, send_task_eager_aware} from here never hit a partially
# initialized module (integration 2026-09-30).
try:
    register_all_tasks(celery_app)
except Exception as exc:  # noqa: BLE001 - importing worker.py must never fail
    logger.warning("task registration incomplete at import time: %s", exc)
