"""Helpers that produce AI SDK v6 ``DataChunk``s for chat telemetry.

Every ``data-*`` UI part the frontend renders starts life here or in a tool.
Emitted via ``get_stream_writer`` alongside the agent's v6 chunks so the
frontend sees them as native ``DataUIPart``s on the assistant message.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, JsonValue
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

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


def enrichment_results_event(
    *,
    task_id: UUID,
    gene_set_id: str,
    gene_set_name: str,
    gene_count: int,
    results: list[dict[str, object]],
    downloads: dict[str, str | int] | None = None,
) -> DataChunk:
    return DataChunk(
        type="data-enrichment-results",
        data={
            "taskId": str(task_id),
            "geneSetId": gene_set_id,
            "geneSetName": gene_set_name,
            "geneCount": gene_count,
            "results": results,
            "downloads": downloads,
        },
    )


def conversation_title_event(*, title: str) -> DataChunk:
    return DataChunk(
        type="data-conversation-title",
        data={"title": title},
    )


def scratchpad_updated_event() -> DataChunk:
    """Chunk that instructs the client to invalidate its scratchpad query."""
    return DataChunk(type="data-scratchpad-updated", data={})


def turn_usage_event(*, total_tokens: int, cost_usd: str) -> DataChunk:
    """Cumulative tokens + cost for the current turn, emitted per phase."""
    return DataChunk(
        type="data-turn-usage",
        data={"totalTokens": total_tokens, "costUsd": cost_usd},
    )


def turn_status_event(*, label: str, waiting_on_llm: bool = False) -> DataChunk:
    """Live status hint for the placeholder shown before the first message
    part arrives. ``waiting_on_llm`` lets the UI distinguish real thinking
    from preparatory work."""
    return DataChunk(
        type="data-turn-status",
        data={"label": label, "waitingOnLlm": waiting_on_llm},
    )


class SubAgentCallPayload(CamelModel):
    """Payload for the ``data-sub-agent-call`` chunk.

    ``tool_call_id`` is the Lead's tool_call_id for this dispatch; the
    frontend joins ``data-sub-agent-step`` chunks to it via
    ``parentToolCallId``.
    """

    tool_call_id: str
    sub_agent: str
    phase: str
    state: Literal["started", "completed", "failed"]
    model_id: str = ""
    summary: str = ""
    succeeded: bool | None = None


def sub_agent_call_event(payload: SubAgentCallPayload) -> DataChunk:
    """Rich UI for one Lead-issued sub-agent dispatch."""
    return DataChunk(
        type="data-sub-agent-call",
        data=payload.model_dump(by_alias=True, mode="json"),
    )


def ledger_update_event(*, ledger: BaseModel) -> DataChunk:
    """``data-ledger-update`` chunk: structured Investigation Ledger
    snapshot.

    Emitted by the Lead node every time the Ledger is re-derived (after
    each sub-agent dispatch). The frontend renders the LedgerPanel as a
    typed read-only UI — boolean badges, count chips, status pills —
    from this payload.
    """
    return DataChunk(
        type="data-ledger-update",
        data=ledger.model_dump(by_alias=True, mode="json", exclude_none=True),
    )


class SubAgentStepPayload(CamelModel):
    """Payload for the ``data-sub-agent-step`` chunk — one event inside
    a sub-agent's run.

    Lets the frontend render each sub-agent dispatch as its own mini
    chat — inner tool calls, reasoning, text — nested under the
    ``data-sub-agent-call`` card with matching ``parentToolCallId``.
    """

    parent_tool_call_id: str
    kind: Literal["tool", "reasoning", "text"]
    state: Literal["started", "completed", "failed"]
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
