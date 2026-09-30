"""Celery background tasks.

STATUS: scaffold stub — not implemented.
"""

from typing import Any
from celery import Task

from app.core.events import publish_event
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def profile_dataset_task(self: Task, dataset_id: str) -> dict[str, Any]:
    """Execute background profiling task for a dataset.

    STATUS: scaffold stub
    """
    try:
        publish_event(
            "task_update",
            {"task": "profile_dataset", "dataset_id": dataset_id, "status": "started"},
        )
    except Exception:
        pass
    raise NotImplementedError("profile_dataset_task not started")


@celery_app.task(bind=True, max_retries=3)
def generate_plan_task(self: Task, dataset_id: str) -> dict[str, Any]:
    """Execute background plan generation task for a dataset.

    STATUS: scaffold stub
    """
    try:
        publish_event(
            "task_update",
            {"task": "generate_plan", "dataset_id": dataset_id, "status": "started"},
        )
    except Exception:
        pass
    raise NotImplementedError("generate_plan_task not started")


@celery_app.task(bind=True, max_retries=3)
def execute_plan_task(self: Task, plan_id: str) -> dict[str, Any]:
    """Execute background cleaning plan task.

    STATUS: scaffold stub
    """
    try:
        publish_event(
            "task_update",
            {"task": "execute_plan", "plan_id": plan_id, "status": "started"},
        )
    except Exception:
        pass
    raise NotImplementedError("execute_plan_task not started")
