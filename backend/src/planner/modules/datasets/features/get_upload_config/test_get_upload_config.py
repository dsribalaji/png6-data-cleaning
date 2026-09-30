"""Service-level unit tests for get_upload_config feature."""

from __future__ import annotations

import pytest

from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.get_upload_config.service import (
    get_upload_config_service,
)


@pytest.fixture
def principal() -> RequestPrincipal:
    return RequestPrincipal(user_id=uuid7(), role="viewer")


@pytest.mark.asyncio
async def test_get_upload_config__default_settings__returns_camelCase_limits(
    principal: RequestPrincipal,
) -> None:
    config = await get_upload_config_service(principal=principal)

    assert config.max_file_mb == settings.upload_max_mb
    assert config.allowed_extensions == [".xlsx", ".csv"]
    assert config.loss_threshold_default == settings.loss_threshold_default

    dumped = config.model_dump(by_alias=True)
    assert dumped["maxFileMb"] == settings.upload_max_mb
    assert dumped["allowedExtensions"] == [".xlsx", ".csv"]
    assert dumped["lossThresholdDefault"] == settings.loss_threshold_default


@pytest.mark.asyncio
async def test_get_upload_config__allowed_extensions__only_xlsx_and_csv(
    principal: RequestPrincipal,
) -> None:
    """FR: only .xlsx and .csv are accepted; no other extension leaks in."""
    config = await get_upload_config_service(principal=principal)

    assert set(config.allowed_extensions) == {".xlsx", ".csv"}
    assert ".pdf" not in config.allowed_extensions
    assert ".xls" not in config.allowed_extensions


@pytest.mark.asyncio
async def test_get_upload_config__override_upload_max_mb__reflects_setting(
    principal: RequestPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "upload_max_mb", 1)

    config = await get_upload_config_service(principal=principal)

    assert config.max_file_mb == 1
    assert config.model_dump(by_alias=True)["maxFileMb"] == 1