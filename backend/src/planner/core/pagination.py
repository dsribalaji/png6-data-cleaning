"""Paginated list envelope: { items, page, pageSize, total } (Backend.md)."""

from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class Page(BaseModel, Generic[T]):
    """Standard pagination envelope serialized as camelCase for the API."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    items: list[T]
    page: int
    page_size: int
    total: int


def page_params(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        20, ge=1, le=200, alias="pageSize", description="Items per page"
    ),
) -> tuple[int, int]:
    """FastAPI query dependency returning (page, page_size)."""
    return page, page_size


def build_page(items: list[T], total: int, page: int, page_size: int) -> Page[T]:
    """Helper to build a Page[T] envelope."""
    return Page(items=items, total=total, page=page, page_size=page_size)
