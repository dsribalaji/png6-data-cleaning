"""The ONLY import surface other modules may use (Backend.md)."""

from __future__ import annotations

from fastapi import APIRouter

from planner.modules.datasets.features.dataset_events.router import (
    router as dataset_events_router,
)
from planner.modules.datasets.features.get_dataset.router import (
    router as get_dataset_router,
)
from planner.modules.datasets.features.get_quarantine.router import (
    router as get_quarantine_router,
)
from planner.modules.datasets.features.get_upload_config.router import (
    router as get_upload_config_router,
)
from planner.modules.datasets.features.list_datasets.router import (
    router as list_datasets_router,
)
from planner.modules.datasets.features.upload_dataset.router import (
    router as upload_dataset_router,
)
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead
from planner.modules.datasets.helpers import (
    create_job,
    get_dataset_or_404,
    replay_job_events,
    update_job,
)
from planner.modules.datasets.models import Dataset, Job, QuarantineRecord

# Canonical router order per Backend.md contract
routers: list[APIRouter] = [
    upload_dataset_router,
    list_datasets_router,
    get_dataset_router,
    get_quarantine_router,
    get_upload_config_router,
    dataset_events_router,
]

__all__ = [
    "Dataset",
    "DatasetRead",
    "Job",
    "QuarantineRecord",
    "create_job",
    "get_dataset",
    "get_dataset_or_404",
    "replay_job_events",
    "routers",
    "update_dataset_status",
    "update_job",
]


async def get_dataset(session, dataset_id):
    """Return the Dataset row for *dataset_id*, or None.

    Integration 2026-09-30: profiling/execution tasks load the ingested
    Parquet via ``dataset.ingested_object_key`` through this function.
    """
    from uuid import UUID

    from planner.modules.datasets.models import Dataset as _Dataset

    if not isinstance(dataset_id, UUID):
        dataset_id = UUID(str(dataset_id))
    return await session.get(_Dataset, dataset_id)


async def update_dataset_status(session, dataset_id, status: str):
    """Set the dataset status. Integration 2026-09-30."""

    dataset = await get_dataset(session, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")
    dataset.status = status
    await session.flush()
    return dataset
