"""Builders for the AI SDK ``DataChunk``s that carry runtime telemetry to the
frontend as data parts on the assistant message."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import JsonValue
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.assistant_core.memory.store import StoredMemory
from pathfinder.platform.pydantic_base import CamelModel


def background_task_started_event(
    *,
    task_id: UUID,
    tool_name: str,
    estimated_duration_seconds: int,
) -> DataChunk:
    return DataChunk(
        type="data-background-task-started",
        data={
            "taskId": str(task_id),
            "toolName": tool_name,
            "estimatedDurationSeconds": estimated_duration_seconds,
        },
    )


class ConversationTitlePayload(CamelModel):
    """Payload for the conversation-title chunk."""

    title: str


def conversation_title_event(*, title: str) -> DataChunk:
    return DataChunk(
        type="data-conversation-title",
        data=ConversationTitlePayload(title=title).model_dump(
            by_alias=True,
            mode="json",
        ),
    )


class MemoryRetrievedItem(CamelModel):
    """One recalled memory in the memory-retrieved chunk."""

    key: str
    kind: str
    name: str
    summary: str
    score: float


class MemoryRetrievedPayload(CamelModel):
    memories: list[MemoryRetrievedItem]


def memory_retrieved_event(*, memories: list[StoredMemory]) -> DataChunk:
    """Report the memories recalled at turn start. The score is the vector
    similarity, and an absent score becomes ``0.0``."""
    payload = MemoryRetrievedPayload(
        memories=[
            MemoryRetrievedItem(
                key=m.key,
                kind=m.value.kind,
                name=m.value.name,
                summary=m.value.summary,
                score=m.score if m.score is not None else 0.0,
            )
            for m in memories
        ],
    )
    return DataChunk(
        type="data-memory-retrieved",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def scratchpad_updated_event() -> DataChunk:
    """Tell the client to invalidate its scratchpad query."""
    return DataChunk(type="data-scratchpad-updated", data={})


def turn_usage_event(*, total_tokens: int, cost_usd: str) -> DataChunk:
    """Report the running token count and cost for the turn.

    The chunk is transient. The persisted total comes from message metadata
    instead.
    """
    return DataChunk(
        type="data-turn-usage",
        data={"totalTokens": total_tokens, "costUsd": cost_usd},
        transient=True,
    )


class LeadUsagePayload(CamelModel):
    """Payload for the lead-usage chunk. The counts cover the Lead agent only
    and exclude sub-agents.
    """

    model_id: str = ""
    tokens: int = 0
    cost_usd: str = "0"


def lead_usage_event(*, model_id: str, tokens: int, cost_usd: str) -> DataChunk:
    """Report live Lead usage. The id is stable, so repeated emissions
    reconcile into one persisted part."""
    return DataChunk(
        type="data-lead-usage",
        id="lead-usage",
        data=LeadUsagePayload(
            model_id=model_id,
            tokens=tokens,
            cost_usd=cost_usd,
        ).model_dump(by_alias=True, mode="json"),
    )


class TurnStoppedPayload(CamelModel):
    """Payload for the turn-stopped chunk. The chunk persists as a message
    part, so the stopped state survives a page reload.
    """


def turn_stopped_event() -> DataChunk:
    return DataChunk(
        type="data-turn-stopped",
        data=TurnStoppedPayload().model_dump(by_alias=True, mode="json"),
    )


class TurnStatusPayload(CamelModel):
    """Payload for the turn-status chunk. The model id travels on the first
    status of a turn only.
    """

    label: str
    waiting_on_llm: bool = False
    model: str | None = None


def turn_status_event(
    *,
    label: str,
    waiting_on_llm: bool = False,
    model: str | None = None,
) -> DataChunk:
    """Report a status hint while the turn runs."""
    return DataChunk(
        type="data-turn-status",
        data=TurnStatusPayload(
            label=label,
            waiting_on_llm=waiting_on_llm,
            model=model,
        ).model_dump(by_alias=True, mode="json", exclude_none=True),
    )


class SubAgentCallPayload(CamelModel):
    """Payload for the sub-agent-call chunk. The tool call id identifies the
    dispatch, and sub-agent step chunks join to it.
    """

    tool_call_id: str
    sub_agent: str
    phase: str
    state: Literal["started", "completed", "failed"]
    model_id: str = ""
    summary: str = ""
    succeeded: bool | None = None
    tokens: int = 0
    cost_usd: str = "0"


def sub_agent_call_event(payload: SubAgentCallPayload) -> DataChunk:
    """Report one sub-agent dispatch. The id is the tool call id, so the
    started and completed emissions reconcile into one part."""
    return DataChunk(
        type="data-sub-agent-call",
        id=payload.tool_call_id,
        data=payload.model_dump(by_alias=True, mode="json"),
    )


class SubAgentStepPayload(CamelModel):
    """Payload for one event inside a sub-agent run. The parent tool call id
    nests the event under its dispatch.
    """

    parent_tool_call_id: str
    kind: Literal["tool", "reasoning", "text"]
    state: Literal["started", "completed", "failed", "denied"]
    tool_call_id: str | None = None
    tool_name: str | None = None
    args: dict[str, JsonValue] | None = None
    result_summary: str | None = None
    text: str | None = None


def sub_agent_step_event(payload: SubAgentStepPayload) -> DataChunk:
    """One event inside a sub-agent's run."""
    return DataChunk(
        type="data-sub-agent-step",
        data=payload.model_dump(by_alias=True, mode="json"),
    )
