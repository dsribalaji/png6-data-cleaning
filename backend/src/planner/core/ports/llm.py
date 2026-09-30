"""LLM port (Backend.md, FR-048).

One port: LlmGateway.complete(task, payload, out). The only implementation
lives in planner/llm/gateway.py, the single file that imports litellm.
"""

from __future__ import annotations

from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

LlmTask = Literal["infer_rules", "propose_steps"]


class LlmGatewayPort(Protocol):
    """Port interface for LLM completions returning structured Pydantic models."""

    async def complete(
        self,
        task: LlmTask | str,
        payload: BaseModel,
        out: type[T],
    ) -> T:
        """Run one LLM task with a Pydantic-typed output model."""
        ...
