from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Interrupt
from pydantic import BaseModel, ValidationError
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.stream_events import background_task_started_event
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.session import async_session_factory
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session


async def _ensure_chat_row(
    session: AsyncSession,
    conversation_id: UUID,
    *,
    user_id: UUID,
    site_id: str,
    experiment_id: str | None,
) -> None:
    existing = await session.get(Conversation, conversation_id)
    if existing is None:
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id=site_id,
                name="",
                experiment_id=experiment_id,
            ),
        )
        await session.flush()
        return
    if experiment_id and existing.experiment_id != experiment_id:
        existing.experiment_id = experiment_id
        await session.flush()


async def _persist_user_message(
    session: AsyncSession, incoming: ChatRequestBody,
) -> None:
    repo = MessagesRepository(session)
    text = incoming.last_user_text
    await repo.insert_message(
        message_id=incoming.last_user_message_id,
        conversation_id=incoming.conversation_id,
        role="user",
        parts=[{"type": "text", "text": text}],
        metadata={"siteId": incoming.site_id, "mode": incoming.mode},
    )


def resolve_site_id(
    *,
    chat_site_id: str | None,
    body_site_id: str,
    conversation_id: UUID,
) -> str:
    if chat_site_id is not None and chat_site_id.strip() != "":
        return chat_site_id
    if body_site_id.strip() != "":
        return body_site_id
    msg = (
        f"site_id could not be resolved for chat {conversation_id}: "
        f"conversation.site_id={chat_site_id!r}, body.site_id={body_site_id!r}"
    )
    raise ValueError(msg)


def _build_runtime_context(
    *,
    conversation: Conversation | None,
    site_id: str,
    user_id: UUID,
    memory_store: AsyncPostgresStore | None,
) -> Context:
    persisted: PersistedStrategyGraph | None = None
    experiment_id: str | None = None
    if conversation is not None:
        plan_payload: StrategyAst | None = None
        if conversation.strategy_ast and "root" in conversation.strategy_ast:
            try:
                plan_payload = StrategyAst.model_validate(conversation.strategy_ast)
            except (ValueError, KeyError, TypeError):
                plan_payload = None
        persisted = PersistedStrategyGraph(
            id=str(conversation.id),
            name=conversation.name,
            strategy_ast=plan_payload,
            wdk_strategy_id=conversation.wdk_strategy_id,
        )
        experiment_id = conversation.experiment_id

    strategy_session = build_strategy_session(
        site_id=site_id, strategy_graph=persisted,
    )
    return Context(
        site_id=site_id,
        user_id=user_id,
        strategy_session=strategy_session,
        db_session_factory=async_session_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        memory_store=memory_store,
        experiment_id=experiment_id,
    )


def _build_turn_input(
    incoming: ChatRequestBody, user_id: UUID, *, turn_message_id: UUID,
) -> dict[str, Any]:
    user_message_id = incoming.last_user_message_id
    user_text = incoming.last_user_text
    return {
        "conversation_id": incoming.conversation_id,
        "user_id": user_id,
        "site_id": incoming.site_id,
        "mode": incoming.mode,
        "user_message_id": user_message_id,
        "user_prompt": user_text,
        "user_parts": [TextUIPart(text=user_text, state="done")],
        "turn_trace_id": str(uuid4()),
        "turn_created_at": datetime.now(UTC).isoformat(),
        "turn_message_id": turn_message_id,
        "supervisor_call_count": 0,
        "phase_call_counts": {},
        "current_phase": None,
        "last_routing_reason": None,
        "last_assistant_prose": "",
        "last_phase_outcome": None,
        "last_verification_message_id": None,
        "turn_message_parts": [],
        "turn_total_tokens": 0,
        "turn_total_cost_usd": Decimal(0),
        "retrieved_memories": [],
    }


class _ChunkEnvelope(BaseModel):
    chunk: dict[str, Any]


def _extract_chunk(payload: object) -> dict[str, Any] | None:
    """Pull a v6 chunk dict out of the ``{"chunk": {...}}`` writer envelope."""
    if not isinstance(payload, dict):
        return None
    try:
        envelope = _ChunkEnvelope.model_validate(payload)
    except ValidationError:
        return None
    return envelope.chunk


_INTERRUPT_KEY: str = "__interrupt__"


class _DurableInterruptPayload(BaseModel):
    """Typed shape of the value passed to ``interrupt()`` by ``@durable_tool``."""

    kind: Literal["durable_task"]
    task_id: str
    tool_name: str
    estimated_duration_seconds: int


def _iter_raw_interrupts(
    payload: object,
) -> list[tuple[Interrupt, _DurableInterruptPayload]]:
    if not isinstance(payload, dict):
        return []
    raw_interrupts = payload.get(_INTERRUPT_KEY)
    if not isinstance(raw_interrupts, tuple | list):
        return []
    parsed: list[tuple[Interrupt, _DurableInterruptPayload]] = []
    for item in raw_interrupts:
        if not isinstance(item, Interrupt):
            continue
        try:
            durable = _DurableInterruptPayload.model_validate(
                item.value, strict=False,
            )
        except ValidationError:
            continue
        parsed.append((item, durable))
    return parsed


def _interrupt_chunks(payload: object) -> Iterator[dict[str, Any]]:
    """Yield one ``data-background-task-started`` chunk per durable interrupt."""
    raw = _iter_raw_interrupts(payload)
    for _, durable in raw:
        chunk = background_task_started_event(
            task_id=UUID(durable.task_id),
            tool_name=durable.tool_name,
            estimated_duration_seconds=durable.estimated_duration_seconds,
        )
        yield chunk.model_dump(by_alias=True, mode="json", exclude_none=True)
