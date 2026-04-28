"""Builders for ValidateContext and ResearchContext.

Slots are populated from existing LangGraph state, the conversation row,
the messages table, the background_tasks table, and the memory store.
The two LLM-extracted slots (user_success_criteria, biological_focus)
run in parallel via :mod:`pathfinder.ai.specialists.extraction`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.specialists.extraction import (
    extract_biological_focus,
    extract_success_criteria,
)
from pathfinder.ai.specialists.types import (
    ControlTestRun,
    ResearchContext,
    StepKind,
    StepSummary,
    TurnExcerpt,
    ValidateContext,
)
from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import (
    BackgroundTask,
    Conversation,
    Message,
)
from pathfinder.persistence.repositories.message import MessagesRepository

_RECENT_TURN_LIMIT: int = 5
_RECENT_TURN_TEXT_CAP: int = 2000
_RECENT_TURNS_TOTAL_BUDGET: int = 6000
"""Aggregate char budget across all `recent_turns` text fields. Per spec
risk J.4, after the per-turn cap we additionally truncate the oldest
turns first if the cumulative text exceeds this budget. Keeps the
specialist's system message bounded even when recent turns are
long-form text + reasoning."""

ControlTaskStatus = ControlTestRun.model_fields["status"].annotation


class _RawControlTestArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step_id: int


class _RawControlTestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""


class _RawTextPart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    text: str = ""


def _step_summaries(conversation: Conversation) -> list[StepSummary]:
    raw = conversation.strategy_ast
    if not raw:
        return []
    try:
        parsed = StrategyAst.model_validate(raw)
    except ValidationError:
        return []
    if (
        conversation.wdk_strategy_id is not None
        and not parsed.wdk_step_ids
    ):
        msg = (
            f"Conversation {conversation.id} has wdk_strategy_id="
            f"{conversation.wdk_strategy_id} but empty wdk_step_ids; "
            "strategy must be re-pushed to WDK before validate-mode can "
            "address steps by their numeric id."
        )
        raise RuntimeError(msg)
    wdk_ids = parsed.wdk_step_ids or {}
    record_type = (
        parsed.record_type or conversation.record_type or ""
    )
    out: list[StepSummary] = []
    for node in walk_step_tree(parsed.root):
        kind = cast("StepKind", node.infer_kind())
        out.append(
            StepSummary(
                step_id=wdk_ids.get(node.id),
                local_step_id=node.id,
                kind=kind,
                display_name=node.display_name or node.search_name,
                search_name=node.search_name,
                record_class_name=record_type,
            ),
        )
    return out


def _control_run_status(raw: str) -> str:
    if raw == "complete":
        return "succeeded"
    if raw == "failed":
        return "failed"
    if raw == "cancelled":
        return "cancelled"
    return "running"


def _control_test_runs(rows: list[BackgroundTask]) -> list[ControlTestRun]:
    out: list[ControlTestRun] = []
    for row in rows:
        if row.tool_name != "run_control_tests_on_step":
            continue
        try:
            args = _RawControlTestArgs.model_validate(row.args or {})
        except (TypeError, ValueError):
            continue
        try:
            result = _RawControlTestResult.model_validate(row.result or {})
        except (TypeError, ValueError):
            result = _RawControlTestResult()
        out.append(
            ControlTestRun.model_validate({
                "task_id": row.id,
                "step_id": args.step_id,
                "status": _control_run_status(row.status),
                "summary": result.summary,
                "completed_at": row.completed_at,
            }),
        )
    return out


def _excerpt_from_message(msg: Message) -> TurnExcerpt:
    text_chunks: list[str] = []
    tool_call_count = 0
    for part_raw in msg.parts or []:
        try:
            part = _RawTextPart.model_validate(part_raw)
        except (TypeError, ValueError):
            continue
        if part.type == "text" and part.text.strip():
            text_chunks.append(part.text.strip())
        elif part.type == "reasoning" and part.text.strip():
            text_chunks.append(f"[reasoning] {part.text.strip()}")
        elif part.type.startswith("tool-"):
            tool_call_count += 1
    role = "user" if msg.role == "user" else "assistant"
    text = "\n".join(text_chunks)[:_RECENT_TURN_TEXT_CAP]
    return TurnExcerpt(
        role=role,
        text=text,
        tool_call_count=tool_call_count,
        created_at=msg.created_at,
    )


def _enforce_total_budget(
    excerpts: list[TurnExcerpt], *, budget: int = _RECENT_TURNS_TOTAL_BUDGET,
) -> list[TurnExcerpt]:
    """Drop the oldest excerpts first until total text length fits in budget.

    Per spec risk J.4: per-turn cap alone is not enough — five turns at
    2000 chars each is 10K chars, which can blow the system message
    budget for chatty conversations. Truncating oldest-first preserves
    the most relevant context (the turns the user just had).
    """
    total = sum(len(e.text) for e in excerpts)
    if total <= budget:
        return excerpts
    out = list(excerpts)
    while out and sum(len(e.text) for e in out) > budget:
        out.pop(0)
    return out


async def _recent_turns(
    session: AsyncSession, conversation_id: UUID,
) -> list[TurnExcerpt]:
    rows = await MessagesRepository(session).list_messages_for_conversation(
        conversation_id,
    )
    rows = [r for r in rows if r.role in ("user", "assistant")]
    last = rows[-_RECENT_TURN_LIMIT:]
    excerpts = [_excerpt_from_message(m) for m in last]
    return _enforce_total_budget(excerpts)


async def _list_conversation_background_tasks(
    session: AsyncSession, conversation_id: UUID,
) -> list[BackgroundTask]:
    result = await session.execute(
        select(BackgroundTask).where(
            BackgroundTask.conversation_id == conversation_id,
        ),
    )
    return list(result.scalars().all())


async def _relevant_memories(
    *,
    memory_store: MemoryStore | None,
    user_id: UUID,
    site_id: str,
    query: str,
) -> list[MemoryValue]:
    if memory_store is None or not query.strip():
        return []
    return await retrieve_relevant_memories(
        store=memory_store,
        user_id=user_id,
        query=query,
        site_id=site_id,
        top_k=5,
    )


def _render_strategy_summary(steps: list[StepSummary]) -> str:
    if not steps:
        return "(no strategy yet — empty conversation)"
    parts = [
        (
            f"Step {s.step_id if s.step_id is not None else s.local_step_id} "
            f"({s.kind}): {s.display_name} (search={s.search_name})"
        )
        for s in steps
    ]
    return "; ".join(parts)


async def build_validate_context(
    *,
    session: AsyncSession,
    conversation: Conversation,
    focused_step_id: int | None,
    memory_store: MemoryStore | None,
    extraction_model_id: str | None = None,
) -> ValidateContext:
    steps = _step_summaries(conversation)
    bg_rows = await _list_conversation_background_tasks(
        session, conversation.id,
    )
    control_runs = _control_test_runs(bg_rows)
    recent = await _recent_turns(session, conversation.id)

    criteria, memories = await asyncio.gather(
        extract_success_criteria(
            recent_turns=recent, model_id=extraction_model_id,
        ),
        _relevant_memories(
            memory_store=memory_store,
            user_id=conversation.user_id,
            site_id=conversation.site_id,
            query=conversation.name or "validate",
        ),
    )

    return ValidateContext(
        strategy_name=conversation.name or "(unnamed)",
        steps=steps,
        focused_step_id=focused_step_id,
        user_success_criteria=criteria,
        prior_control_test_runs=control_runs,
        relevant_memories=memories,
        recent_turns=recent,
    )


async def build_research_context(
    *,
    session: AsyncSession,
    conversation: Conversation,
    research_question: str,
    memory_store: MemoryStore | None,
    extraction_model_id: str | None = None,
) -> ResearchContext:
    steps = _step_summaries(conversation)
    recent = await _recent_turns(session, conversation.id)

    focus, memories = await asyncio.gather(
        extract_biological_focus(
            research_question=research_question,
            recent_turns=recent,
            model_id=extraction_model_id,
        ),
        _relevant_memories(
            memory_store=memory_store,
            user_id=conversation.user_id,
            site_id=conversation.site_id,
            query=research_question or conversation.name or "research",
        ),
    )

    return ResearchContext(
        research_question=research_question.strip(),
        current_strategy_summary=_render_strategy_summary(steps),
        biological_focus=focus,
        relevant_memories=memories,
        recent_turns=recent,
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
