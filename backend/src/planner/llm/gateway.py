"""LlmGateway -> LiteLLM adapter. ONLY file in the repo importing litellm/instructor."""

from __future__ import annotations

import json
import os
import pathlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import instructor
import litellm
import structlog
from pydantic import BaseModel, ValidationError

from planner.core.config import settings
from planner.core.errors import AppError
from planner.core.ports.llm import LlmGatewayPort
from planner.llm.cache import LlmCache
from planner.llm.redaction import minimise_payload

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "groq/openai/gpt-oss-120b"
PROMPT_VERSION = "v1"
TASKS: tuple[str, ...] = ("infer_rules", "propose_steps")
LLM_TIMEOUT_S = 120

T = TypeVar("T", bound=BaseModel)


@dataclass
class ResolvedModelConfig:
    """Resolved model configuration and credentials decrypted for execution."""

    provider: str
    model: str
    endpoint_url: str | None = None
    api_key: str | None = None
    allow_data_sharing: bool = False


class LlmError(AppError):
    """Raised when LLM outputs remain invalid after repair retries."""

    def __init__(
        self,
        code: str = "LLM_UNRELIABLE_OUTPUT",
        message: str | None = (
            "The model returned invalid structured output twice; "
            "marked low-confidence, use deterministic heuristics."
        ),
        status: int = 502,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status=status, errors=errors)


class LlmConnectionError(AppError):
    """Raised when the LLM provider cannot be reached."""

    def __init__(
        self,
        code: str = "MODEL_CONNECTION_FAILED",
        message: str | None = "Could not reach the provider. Check the key and endpoint.",
        status: int = 422,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status=status, errors=errors)


def _litellm_model_id(provider: str, model: str) -> str:
    """Ensure litellm model format is provider/model."""
    if model.startswith(f"{provider}/"):
        return model
    return f"{provider}/{model}"


def _load_prompt(
    task: str,
    payload_json: str = "",
    output_schema: str = "",
) -> str:
    """Load prompt template for task and substitute placeholders."""
    prompt_path = pathlib.Path(__file__).parent / "prompts" / f"{task}.v1.md"
    content = prompt_path.read_text(encoding="utf-8")
    if output_schema:
        content = content.replace("{{OUTPUT_SCHEMA}}", output_schema)
    if payload_json:
        content = content.replace("{{PAYLOAD_JSON}}", payload_json)
    return content


def _call_model(
    model_id: str,
    messages: list[dict[str, str]],
    out: type[T],
    api_key: str | None,
    endpoint_url: str | None,
) -> T:
    """Call model using instructor and litellm with structured JSON output."""
    client = instructor.from_litellm(litellm.completion, mode=instructor.Mode.JSON)
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "response_model": out,
        "max_retries": 0,
        "timeout": LLM_TIMEOUT_S,
    }
    if api_key is not None:
        kwargs["api_key"] = api_key
    if endpoint_url is not None:
        kwargs["base_url"] = endpoint_url
    return client.chat.completions.create(**kwargs)  # type: ignore[no-any-return]


async def _default_env_resolver() -> ResolvedModelConfig | None:
    """Default config resolver using environment variables."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        api_key = getattr(settings, "groq_api_key", None)
    allow_data_sharing = os.environ.get("LLM_ALLOW_DATA_SHARING", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    provider = os.environ.get("LLM_PROVIDER", "groq")
    endpoint_url = os.environ.get("LLM_ENDPOINT_URL")
    return ResolvedModelConfig(
        provider=provider,
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
        allow_data_sharing=allow_data_sharing,
    )


async def test_connection(config: ResolvedModelConfig, timeout_s: int = 30) -> float:
    """Test model connection by sending a probe message.

    Returns elapsed seconds on success, or raises LlmConnectionError.
    """
    model_id = _litellm_model_id(config.provider, config.model)
    start = time.monotonic()
    try:
        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with the single word OK."}],
            "timeout": timeout_s,
        }
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.endpoint_url is not None:
            kwargs["base_url"] = config.endpoint_url
        litellm.completion(**kwargs)
        return time.monotonic() - start
    except Exception as exc:
        raise LlmConnectionError() from exc


class LlmGateway(LlmGatewayPort):
    """Model-agnostic LLM gateway using LiteLLM and instructor structured outputs."""

    def __init__(
        self,
        config_resolver: Callable[[], Awaitable[ResolvedModelConfig | None]] | None = None,
        cache: LlmCache | None = None,
    ) -> None:
        self._config_resolver = config_resolver or _default_env_resolver
        self._cache = cache if cache is not None else LlmCache()

    test_connection = staticmethod(test_connection)

    async def complete(self, task: str, payload: BaseModel, out: type[T]) -> T:
        """Run one LLM task with structured output validation, caching, and retry repair."""
        start_time = time.monotonic()

        # 1. Validate task
        if task not in TASKS:
            raise AppError("LLM_UNKNOWN_TASK", f"Unknown LLM task: {task}.", 400)

        # 2. Resolve model configuration
        config = await self._config_resolver()
        if config is None or (not config.api_key and config.provider != "ollama"):
            raise AppError(
                "LLM_NO_CREDENTIAL",
                "No model credential configured. Set GROQ_API_KEY or save a model config.",
                500,
            )

        # 3. Minimise payload according to privacy policy
        min_payload = minimise_payload(
            payload.model_dump(mode="json"),
            allow_data_sharing=config.allow_data_sharing,
        )
        payload_json = json.dumps(min_payload, sort_keys=True, default=str)

        # 4. Prepare prompt and model identifier
        model_id = _litellm_model_id(config.provider, config.model)
        output_schema = json.dumps(out.model_json_schema())
        prompt = _load_prompt(task, payload_json="", output_schema=output_schema)

        # 5. Check cache
        key = self._cache.make_key(config.provider, model_id, PROMPT_VERSION, payload_json)
        cached = await self._cache.get(key)
        if cached is not None:
            try:
                res = out.model_validate_json(cached)
                latency_ms = (time.monotonic() - start_time) * 1000
                logger.info(
                    "llm_complete",
                    task=task,
                    model=model_id,
                    cache_hit=True,
                    latency_ms=round(latency_ms, 2),
                )
                return res
            except Exception:
                # If cached representation fails validation, bypass and re-generate
                pass

        # 6. Build messages with delimited payload block
        user_content = f"<<<PAYLOAD_JSON\n```json\n{payload_json}\n```\n>>>END"
        messages: list[dict[str, str]] = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]

        # 7. Model invocation with 1 repair retry on ValidationError
        try:
            result = _call_model(model_id, messages, out, config.api_key, config.endpoint_url)
        except ValidationError as err1:
            failed_content = (
                getattr(err1, "raw_response", None)
                or getattr(err1, "input_value", None)
                or str(err1)
            )
            messages.append({"role": "assistant", "content": str(failed_content)})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Previous output failed validation: {err1.errors()}. "
                        "Return ONLY corrected JSON matching the schema, no prose."
                    ),
                }
            )
            try:
                result = _call_model(model_id, messages, out, config.api_key, config.endpoint_url)
            except ValidationError as err2:
                raise LlmError(
                    "LLM_UNRELIABLE_OUTPUT",
                    "The model returned invalid structured output twice; "
                    "marked low-confidence, use deterministic heuristics.",
                    502,
                ) from err2

        # 8. Success: populate cache and log safe metadata
        await self._cache.set(key, result.model_dump_json())
        latency_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "llm_complete",
            task=task,
            model=model_id,
            cache_hit=False,
            latency_ms=round(latency_ms, 2),
        )
        return result
