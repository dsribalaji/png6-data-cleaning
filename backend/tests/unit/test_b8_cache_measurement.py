"""B8 end-to-end LLM cache measurement with a counting stub gateway.

Proves that identical requests hit the cache (zero model calls on repetition)
and that cache keys vary with prompt version.

Deterministic and CI-safe: makes no network calls and does NOT import litellm or instructor.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from planner.llm.cache import LlmCache
from planner.llm.gateway import LlmGateway, ResolvedModelConfig


class EchoOut(BaseModel):
    rules: list[str]


class EchoPayload(BaseModel):
    dataset_name: str = "invoices"


async def fake_resolver() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="unit-test-fake-key",
        allow_data_sharing=False,
    )


@pytest.mark.asyncio
async def test_cache__second_identical_call_makes_zero_model_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[dict[str, str]]]] = []

    def stub_call_model(
        model_id: str,
        messages: list[dict[str, str]],
        out: type,
        api_key: str | None,
        endpoint_url: str | None,
    ) -> Any:
        calls.append((model_id, messages))
        return out(rules=["r1"])

    monkeypatch.setattr("planner.llm.gateway._call_model", stub_call_model)

    gateway = LlmGateway(config_resolver=fake_resolver, cache=LlmCache())
    payload = EchoPayload(dataset_name="invoices")

    res1 = await gateway.complete("infer_rules", payload, EchoOut)
    res2 = await gateway.complete("infer_rules", payload, EchoOut)

    assert res1 == EchoOut(rules=["r1"])
    assert res2 == EchoOut(rules=["r1"])
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cache__key_changes_with_prompt_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[dict[str, str]]]] = []

    def stub_call_model(
        model_id: str,
        messages: list[dict[str, str]],
        out: type,
        api_key: str | None,
        endpoint_url: str | None,
    ) -> Any:
        calls.append((model_id, messages))
        return out(rules=["r1"])

    monkeypatch.setattr("planner.llm.gateway._call_model", stub_call_model)

    gateway = LlmGateway(config_resolver=fake_resolver, cache=LlmCache())
    payload = EchoPayload(dataset_name="invoices")

    monkeypatch.setattr("planner.core.config.settings.llm_prompt_version", "v1")
    res1 = await gateway.complete("infer_rules", payload, EchoOut)
    assert res1 == EchoOut(rules=["r1"])
    assert len(calls) == 1

    monkeypatch.setattr("planner.core.config.settings.llm_prompt_version", "v2")
    res2 = await gateway.complete("infer_rules", payload, EchoOut)
    assert res2 == EchoOut(rules=["r1"])
    assert len(calls) == 2

    p = '{"dataset_name": "invoices"}'
    key_v1 = LlmCache().make_key("groq", "groq/openai/gpt-oss-120b", "v1", p)
    key_v2 = LlmCache().make_key("groq", "groq/openai/gpt-oss-120b", "v2", p)
    assert key_v1 != key_v2
    assert key_v1.startswith("llm:")
    assert key_v2.startswith("llm:")
