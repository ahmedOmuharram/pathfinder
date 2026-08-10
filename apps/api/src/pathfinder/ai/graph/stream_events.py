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

from pathfinder.ai.memory.store import StoredMemory
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


class ConversationTitlePayload(CamelModel):
    """Payload for the ``data-conversation-title`` chunk."""

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
    """One recalled memory shown in the ``data-memory-retrieved`` chunk."""

    key: str
    kind: str
    name: str
    summary: str
    score: float


class MemoryRetrievedPayload(CamelModel):
    memories: list[MemoryRetrievedItem]


def memory_retrieved_event(*, memories: list[StoredMemory]) -> DataChunk:
    """Surface the cross-thread memories recalled at turn start.

    Lets the user see what prior context the agent pulled in (and drives the
    rail's recalled-memory badge). ``score`` is the HNSW similarity; ``None``
    (no score on the stored item) collapses to ``0.0``.
    """
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
    """Chunk that instructs the client to invalidate its scratchpad query."""
    return DataChunk(type="data-scratchpad-updated", data={})


def turn_usage_event(*, total_tokens: int, cost_usd: str) -> DataChunk:
    """Cumulative tokens + cost for the current turn, emitted live.

    Transient: a live signal for the footer only. The persisted
    per-conversation total is recomputed from each message's
    ``metadata.usage`` on load, so persisting every delta would just bloat
    the message with hundreds of throwaway parts.
    """
    return DataChunk(
        type="data-turn-usage",
        data={"totalTokens": total_tokens, "costUsd": cost_usd},
        transient=True,
    )


class LeadUsagePayload(CamelModel):
    """Payload for the ``data-lead-usage`` chunk — the Lead agent's own
    model, tokens, and cost (excluding sub-agents). Drives the per-message
    lead badge and updates live as the Lead streams.
    """

    model_id: str = ""
    tokens: int = 0
    cost_usd: str = "0"


def lead_usage_event(*, model_id: str, tokens: int, cost_usd: str) -> DataChunk:
    """Live Lead usage. Stable ``id`` so repeated emissions reconcile into a
    single persisted part rather than one per token delta."""
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
    """Payload for the ``data-turn-stopped`` chunk.

    Emitted when a turn is cancelled (user pressed Stop). Persisted as a
    message part so the "stopped" state survives a page refresh.
    """


def turn_stopped_event() -> DataChunk:
    return DataChunk(
        type="data-turn-stopped",
        data=TurnStoppedPayload().model_dump(by_alias=True, mode="json"),
    )


class TurnStatusPayload(CamelModel):
    """Payload for the ``data-turn-status`` chunk.

    ``waiting_on_llm`` lets the UI distinguish real thinking from
    preparatory work. ``model`` carries the Lead's model id once (on the
    first status of the turn) so the UI can show the Lead's provider icon
    alongside the live status.
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
    """Live status hint shown by the UI while the turn is running."""
    return DataChunk(
        type="data-turn-status",
        data=TurnStatusPayload(
            label=label,
            waiting_on_llm=waiting_on_llm,
            model=model,
        ).model_dump(by_alias=True, mode="json", exclude_none=True),
    )


class StrategyRevisionPayload(CamelModel):
    """Payload for the ``data-strategy-revision`` chunk.

    The fingerprint of the strategy this turn described. The UI compares it
    against the conversation's live revision to mark a message's counts as
    historical once the strategy is edited.
    """

    revision: str


def strategy_revision_event(*, revision: str) -> DataChunk:
    return DataChunk(
        type="data-strategy-revision",
        data=StrategyRevisionPayload(revision=revision).model_dump(
            by_alias=True,
            mode="json",
        ),
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
    tokens: int = 0
    cost_usd: str = "0"


def sub_agent_call_event(payload: SubAgentCallPayload) -> DataChunk:
    """Rich UI for one Lead-issued sub-agent dispatch.

    ``id`` is the tool_call_id so the started/completed emissions reconcile
    into a single UI part that transitions, not two separate cards.
    """
    return DataChunk(
        type="data-sub-agent-call",
        id=payload.tool_call_id,
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
