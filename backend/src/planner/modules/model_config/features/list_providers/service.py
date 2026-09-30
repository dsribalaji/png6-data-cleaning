"""Service for listing available LLM providers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.model_config.features.list_providers.schemas import ProviderInfoOut

STATIC_PROVIDERS: list[ProviderInfoOut] = [
    ProviderInfoOut(
        id="groq",
        label="Groq",
        default_model="openai/gpt-oss-120b",
        needs_endpoint=False,
        needs_key=True,
        recommended=True,
    ),
    ProviderInfoOut(
        id="openai",
        label="OpenAI",
        default_model="gpt-4o",
        needs_endpoint=False,
        needs_key=True,
        recommended=False,
    ),
    ProviderInfoOut(
        id="anthropic",
        label="Anthropic",
        default_model="claude-3-5-sonnet-20241022",
        needs_endpoint=False,
        needs_key=True,
        recommended=False,
    ),
    ProviderInfoOut(
        id="ollama",
        label="Ollama",
        default_model="llama3.1:8b",
        needs_endpoint=True,
        needs_key=False,
        recommended=False,
    ),
    ProviderInfoOut(
        id="vllm",
        label="vLLM",
        default_model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        needs_endpoint=True,
        needs_key=False,
        recommended=False,
    ),
    ProviderInfoOut(
        id="together",
        label="Together AI",
        default_model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        needs_endpoint=False,
        needs_key=True,
        recommended=False,
    ),
    ProviderInfoOut(
        id="fireworks",
        label="Fireworks AI",
        default_model="accounts/fireworks/models/llama-v3p1-70b-instruct",
        needs_endpoint=False,
        needs_key=True,
        recommended=False,
    ),
    ProviderInfoOut(
        id="mistral",
        label="Mistral AI",
        default_model="mistral-large-latest",
        needs_endpoint=False,
        needs_key=True,
        recommended=False,
    ),
]


async def list_providers(
    session: AsyncSession | None = None,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> list[ProviderInfoOut]:
    """Return static list of supported LLM inference providers."""
    return STATIC_PROVIDERS
