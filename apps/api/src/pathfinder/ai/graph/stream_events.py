"""Helpers that produce AI SDK v6 ``DataChunk``s for chat telemetry.

Every ``data-*`` UI part the frontend renders starts life here or in a tool.
Emitted via ``get_stream_writer`` alongside the agent's v6 chunks so the
frontend sees them as native ``DataUIPart``s on the assistant message.
"""
from __future__ import annotations

from uuid import UUID

from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.specialists.types import SpecialistKind


def phase_start_event(*, phase: str, trace_id: str, model: str) -> DataChunk:
    return DataChunk(
        type="data-phase-start",
        data={"phase": phase, "traceId": trace_id, "model": model},
    )


def phase_change_event(*, phase: str, status: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-phase-change",
        data={"phase": phase, "status": status, "reason": reason},
    )


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


def turn_rejected_event(*, message: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-turn-rejected",
        data={"message": message, "reason": reason},
    )


def turn_qa_event(*, answer: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-turn-qa",
        data={"answer": answer, "reason": reason},
    )


def supervisor_decision_event(*, to: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-supervisor-decision",
        data={"to": to, "reason": reason},
    )


def specialist_suggestion_event(*, kind: SpecialistKind) -> DataChunk:
    """``data-specialist-suggestion`` chunk for the supervisor's hint chip."""
    return DataChunk(
        type="data-specialist-suggestion",
        data={"kind": kind},
    )


def specialist_turn_start_event(
    *, kind: SpecialistKind, model_id: str | None,
) -> DataChunk:
    return DataChunk(
        type="data-specialist-turn-start",
        data={"kind": kind, "modelId": model_id},
    )


def scratchpad_updated_event() -> DataChunk:
    """Chunk that instructs the client to invalidate its scratchpad query."""
    return DataChunk(type="data-scratchpad-updated", data={})


def turn_usage_event(*, total_tokens: int, cost_usd: str) -> DataChunk:
    """Cumulative tokens + cost for the current turn, emitted per phase.

    Lets the composer footer update live during the run — and guarantees
    the frontend has an up-to-date figure even when the turn fails before
    ``finalize_turn`` writes the final assistant message.
    """
    return DataChunk(
        type="data-turn-usage",
        data={"totalTokens": total_tokens, "costUsd": cost_usd},
    )
