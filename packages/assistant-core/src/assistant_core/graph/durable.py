"""What a durable tool declares, and the value that answers its parked call.

A durable tool hands its work to a worker and defers its call. The registry
here keeps what the tool declared, so the turn that delivers the worker's
result can build the chunks the tool would have emitted itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import JsonValue
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk

from assistant_core.graph.turn_state import DurableTaskResult, PendingDurableCall

type ChunkBuilder = Callable[[Any, UUID, str | None], list[BaseChunk]]


@dataclass(frozen=True)
class DurableToolSpec:
    """One durable tool, as it declared itself."""

    tool_name: str
    estimated_duration_seconds: int
    chunks_from_result: ChunkBuilder | None = None


DURABLE_TOOLS: dict[str, DurableToolSpec] = {}


def register_durable_tool(spec: DurableToolSpec) -> None:
    """Record a durable tool's declaration under its registered name."""
    DURABLE_TOOLS[spec.tool_name] = spec


def durable_call_id(parked: PendingDurableCall) -> str:
    """The tool call the worker's result answers: the parked call itself, or
    the one inside the sub-agent run the dispatch parked."""
    sub_agent = parked.sub_agent
    if sub_agent is None or not sub_agent.approvals:
        return parked.tool_call_id
    return sub_agent.approvals[0].tool_call_id


def durable_tool_return(
    parked: PendingDurableCall,
    result: DurableTaskResult,
) -> ToolReturn[dict[str, JsonValue]]:
    """The value and the chunks the durable tool would have returned."""
    payload = result.as_tool_value()
    spec = DURABLE_TOOLS.get(parked.durable_tool_name)
    chunks: list[BaseChunk] = []
    if spec is not None and spec.chunks_from_result is not None:
        chunks = spec.chunks_from_result(
            payload,
            parked.task_id,
            durable_call_id(parked),
        )
    return ToolReturn(return_value=payload, metadata=chunks)


__all__ = [
    "DURABLE_TOOLS",
    "ChunkBuilder",
    "DurableToolSpec",
    "durable_call_id",
    "durable_tool_return",
    "register_durable_tool",
]
