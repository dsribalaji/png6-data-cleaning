"""Unit tests for the model_config module (W3)."""

from __future__ import annotations

from typing import Any
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import planner.llm.gateway as gateway
from planner.core.config import settings
from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.model_config.crypto import (
    credential_last4,
    decrypt_credential,
    encrypt_credential,
)
from planner.modules.model_config.errors import (
    CONFIGURATION_ERROR,
    MODEL_CONFIG_NOT_FOUND,
    MODEL_CONNECTION_FAILED,
)
from planner.modules.model_config.features.get_model_config.service import get_model_config
from planner.modules.model_config.features.list_providers.service import list_providers
from planner.modules.model_config.features.test_model_connection.schemas import (
    TestModelConnectionInput,
)
from planner.modules.model_config.features.test_model_connection.service import (
    test_model_connection,
)
from planner.modules.model_config.features.update_model_config.schemas import (
    UpdateModelConfigInput,
)
from planner.modules.model_config.features.update_model_config.service import (
    update_model_config,
)
from planner.modules.model_config.models import ModelConfig
from planner.modules.model_config.public import (
    ResolvedModelConfig,
    get_active_model_config,
    resolve_llm_config,
)


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a valid generated Fernet key in settings."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key)
    return key


@pytest.fixture
async def async_session() -> AsyncSession:
    """Create in-memory SQLite database session with stripped schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # Strip schema for SQLite compatibility
    orig_schema = ModelConfig.__table__.schema
    ModelConfig.__table__.schema = None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[ModelConfig.__table__])

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    ModelConfig.__table__.schema = orig_schema


# ---------------------------------------------------------------------------
# Crypto tests
# ---------------------------------------------------------------------------


def test_crypto_roundtrip(fernet_key: str) -> None:
    """Verify encryption and decryption roundtrip and credential_last4 extraction."""
    plaintext = "gsk_test_secret_credential_12345"
    ciphertext = encrypt_credential(plaintext)
    assert ciphertext != plaintext
    assert decrypt_credential(ciphertext) == plaintext

    assert credential_last4("gsk_test_secret_credential_12345") == "2345"
    assert credential_last4("123") == "123"
    assert credential_last4("") == ""


def test_crypto_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CONFIGURATION_ERROR (500) is raised on missing, change-me, or invalid keys."""
    # Missing key
    monkeypatch.setattr(settings, "fernet_key", "")
    with pytest.raises(AppError) as exc_info:
        encrypt_credential("secret")
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert exc_info.value.status == 500

    # "change-me" placeholder
    monkeypatch.setattr(settings, "fernet_key", "change-me-before-production")
    with pytest.raises(AppError) as exc_info:
        encrypt_credential("secret")
    assert exc_info.value.code == "CONFIGURATION_ERROR"

    # Invalid key
    monkeypatch.setattr(settings, "fernet_key", "not-a-valid-fernet-key")
    with pytest.raises(AppError) as exc_info:
        encrypt_credential("secret")
    assert exc_info.value.code == "CONFIGURATION_ERROR"

    # Decrypt with invalid key
    with pytest.raises(AppError) as exc_info:
        decrypt_credential("garbage-ciphertext")
    assert exc_info.value.code == "CONFIGURATION_ERROR"


# ---------------------------------------------------------------------------
# Service tests on SQLite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_model_config_empty_raises_404(async_session: AsyncSession) -> None:
    """GET when table is empty raises MODEL_CONFIG_NOT_FOUND (404)."""
    with pytest.raises(AppError) as exc_info:
        await get_model_config(async_session)
    assert exc_info.value.code == "MODEL_CONFIG_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_update_creates_active_row(
    async_session: AsyncSession, fernet_key: str
) -> None:
    """First update creates active row with encrypted ciphertext and last4."""
    payload = UpdateModelConfigInput(
        provider="groq",
        model="openai/gpt-oss-120b",
        credential="gsk_supersecretkey1234",
        allow_data_sharing=True,
    )
    result = await update_model_config(async_session, payload)
    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-120b"
    assert result.credential_last4 == "1234"
    assert result.allow_data_sharing is True
    assert result.is_active is True
    assert result.updated_at is not None

    # Check database row directly
    db_result = await async_session.execute(
        select(ModelConfig).where(ModelConfig.is_active.is_(True))
    )
    row = db_result.scalar_one()
    assert row.credential_ciphertext != "gsk_supersecretkey1234"
    assert decrypt_credential(row.credential_ciphertext) == "gsk_supersecretkey1234"
    assert row.credential_last4 == "1234"
    assert row.is_active is True


@pytest.mark.asyncio
async def test_second_update_deactivates_old_rows(
    async_session: AsyncSession, fernet_key: str
) -> None:
    """Second update deactivates prior rows leaving exactly one active row."""
    # First update
    first_payload = UpdateModelConfigInput(
        provider="groq",
        model="openai/gpt-oss-120b",
        credential="gsk_key1_1111",
        allow_data_sharing=False,
    )
    await update_model_config(async_session, first_payload)

    # Second update
    second_payload = UpdateModelConfigInput(
        provider="groq",
        model="openai/gpt-oss-new",
        credential="gsk_key2_2222",
        allow_data_sharing=True,
    )
    res2 = await update_model_config(async_session, second_payload)
    assert res2.model == "openai/gpt-oss-new"
    assert res2.credential_last4 == "2222"
    assert res2.is_active is True

    # Check DB state
    all_rows = (await async_session.execute(select(ModelConfig))).scalars().all()
    assert len(all_rows) == 2

    active_rows = [r for r in all_rows if r.is_active]
    inactive_rows = [r for r in all_rows if not r.is_active]

    assert len(active_rows) == 1
    assert active_rows[0].model == "openai/gpt-oss-new"
    assert len(inactive_rows) == 1
    assert inactive_rows[0].model == "openai/gpt-oss-120b"

    # get_model_config returns the active one
    current = await get_model_config(async_session)
    assert current.model == "openai/gpt-oss-new"


@pytest.mark.asyncio
async def test_update_preserves_existing_credential_when_none(
    async_session: AsyncSession, fernet_key: str
) -> None:
    """Updating without a new credential preserves the previous key and last4."""
    initial = UpdateModelConfigInput(
        provider="groq",
        model="openai/gpt-oss-120b",
        credential="gsk_initial_9999",
    )
    await update_model_config(async_session, initial)

    update_payload = UpdateModelConfigInput(
        provider="groq",
        model="openai/gpt-oss-updated",
        credential=None,  # Do not change credential
        allow_data_sharing=True,
    )
    res = await update_model_config(async_session, update_payload)
    assert res.credential_last4 == "9999"
    assert res.model == "openai/gpt-oss-updated"

    # Verify decrypt still matches initial credential
    active = (
        await async_session.execute(
            select(ModelConfig).where(ModelConfig.is_active.is_(True))
        )
    ).scalar_one()
    assert decrypt_credential(active.credential_ciphertext) == "gsk_initial_9999"


@pytest.mark.asyncio
async def test_test_model_connection_success(
    async_session: AsyncSession, fernet_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connection test succeeds returning latency in ms."""
    await update_model_config(
        async_session,
        UpdateModelConfigInput(
            provider="groq",
            model="openai/gpt-oss-120b",
            credential="gsk_activekey",
        ),
    )

    async def mock_test_connection(cfg: ResolvedModelConfig) -> int:
        assert cfg.provider == "groq"
        assert cfg.model == "openai/gpt-oss-120b"
        assert cfg.api_key == "gsk_activekey"
        return 42

    monkeypatch.setattr(gateway, "test_connection", mock_test_connection)

    res = await test_model_connection(async_session)
    assert res.ok is True
    assert res.latency_ms == 42


@pytest.mark.asyncio
async def test_test_model_connection_with_overrides(
    async_session: AsyncSession, fernet_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connection test uses provided overrides without modifying saved row."""
    await update_model_config(
        async_session,
        UpdateModelConfigInput(
            provider="groq",
            model="openai/gpt-oss-120b",
            credential="gsk_activekey",
        ),
    )

    captured_config: list[ResolvedModelConfig] = []

    async def mock_test_connection(cfg: ResolvedModelConfig) -> int:
        captured_config.append(cfg)
        return 75

    monkeypatch.setattr(gateway, "test_connection", mock_test_connection)

    overrides = TestModelConnectionInput(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        credential="sk-ant-override",
    )
    res = await test_model_connection(async_session, overrides)
    assert res.ok is True
    assert res.latency_ms == 75
    assert len(captured_config) == 1
    assert captured_config[0].provider == "anthropic"
    assert captured_config[0].model == "claude-3-5-sonnet-20241022"
    assert captured_config[0].api_key == "sk-ant-override"

    # Verify active row is still groq
    current = await get_model_config(async_session)
    assert current.provider == "groq"


@pytest.mark.asyncio
async def test_test_model_connection_failure_propagates_422(
    async_session: AsyncSession, fernet_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connection test failure propagates as 422 error."""
    await update_model_config(
        async_session,
        UpdateModelConfigInput(
            provider="groq",
            model="openai/gpt-oss-120b",
            credential="gsk_badkey",
        ),
    )

    async def mock_failing_connection(cfg: ResolvedModelConfig) -> int:
        raise gateway.LlmConnectionError(message="Connection refused by provider")

    monkeypatch.setattr(gateway, "test_connection", mock_failing_connection)

    with pytest.raises(AppError) as exc_info:
        await test_model_connection(async_session)
    assert exc_info.value.status == 422
    assert exc_info.value.code == "MODEL_CONNECTION_FAILED"


@pytest.mark.asyncio
async def test_test_model_connection_no_config_raises_404(
    async_session: AsyncSession,
) -> None:
    """Connection test without active config or provider overrides raises 404."""
    with pytest.raises(AppError) as exc_info:
        await test_model_connection(async_session)
    assert exc_info.value.code == "MODEL_CONFIG_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_list_providers() -> None:
    """Providers list contains groq with defaultModel 'openai/gpt-oss-120b' and recommended true."""
    providers = await list_providers()
    assert len(providers) >= 8

    by_id = {p.id: p for p in providers}
    assert "groq" in by_id
    groq = by_id["groq"]
    assert groq.label == "Groq"
    assert groq.default_model == "openai/gpt-oss-120b"
    assert groq.recommended is True
    assert groq.needs_key is True
    assert groq.needs_endpoint is False

    assert "ollama" in by_id
    assert by_id["ollama"].needs_endpoint is True
    assert by_id["ollama"].needs_key is False

    assert "vllm" in by_id
    assert by_id["vllm"].needs_endpoint is True

    for pid in ["openai", "anthropic", "together", "fireworks", "mistral"]:
        assert pid in by_id


@pytest.mark.asyncio
async def test_public_api(async_session: AsyncSession, fernet_key: str) -> None:
    """Verify get_active_model_config and resolve_llm_config public functions."""
    # When empty
    assert await get_active_model_config(async_session) is None
    assert await resolve_llm_config(async_session) is None

    # After saving config
    await update_model_config(
        async_session,
        UpdateModelConfigInput(
            provider="groq",
            model="openai/gpt-oss-120b",
            credential="gsk_secret_for_public_api",
            allow_data_sharing=True,
        ),
    )

    active = await get_active_model_config(async_session)
    assert active is not None
    assert active.provider == "groq"
    assert active.is_active is True

    resolved = await resolve_llm_config(async_session)
    assert resolved is not None
    assert resolved.provider == "groq"
    assert resolved.model == "openai/gpt-oss-120b"
    assert resolved.api_key == "gsk_secret_for_public_api"
    assert resolved.allow_data_sharing is True
