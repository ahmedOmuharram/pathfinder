"""Conversation turn dispatcher — AI SDK v6 UI Message Stream over SSE.

The frontend submits via ``@ai-sdk/react``'s ``useChat``; pydantic-ai's
``VercelAIAdapter`` is the canonical on-the-wire format. Each LangGraph
phase node emits v6 chunks via ``get_stream_writer`` (see
:mod:`pathfinder.ai.conversation.vercel_adapter`), this dispatcher wraps them in a
single ``StartChunk`` / ``FinishChunk`` / ``DoneChunk`` envelope per turn
and SSE-encodes the result.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Interrupt
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai.ui.vercel_ai._event_stream import VERCEL_AI_DSP_HEADERS
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    StartChunk,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response, StreamingResponse

from pathfinder.ai.conversation.title_generator import generate_conversation_title
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import (
    background_task_started_event,
    conversation_title_event,
)
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import (
    ConversationRepository,
    MessagesRepository,
)
from pathfinder.persistence.repositories.conversation import ConversationUpdate
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)

DoneReason = Literal["completed", "interrupted", "error"]


# ─────────────────────────── request body (v6) ──────────────────────────


class _UIMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: Literal["system", "user", "assistant"]
    parts: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequestBody(CamelModel):
    """Typed body for ``POST /api/v1/chat`` (AI SDK v6 + PathFinder extras).

    The shape matches ``@ai-sdk/react``'s ``useChat`` submit payload
    (``trigger``, ``id``, ``messages``) with PathFinder-scoped fields
    (``conversationId``, ``siteId``, ``mode``, ``experimentId``) layered on
    via ``body`` on the client transport. The authenticated user UUID still
    comes from the ``pathfinder-auth`` cookie.
    """

    model_config = ConfigDict(extra="ignore")

    trigger: Literal["submit-message", "regenerate-message"] = "submit-message"
    id: str = ""
    messages: list[_UIMessage] = Field(default_factory=list)

    conversation_id: UUID
    site_id: str = ""
    mode: str = "strategy"
    experiment_id: str | None = None
    user_message_id: UUID = Field(default_factory=uuid4)

    @property
    def last_user_text(self) -> str:
        """Extract the concatenated text of the last user message's parts."""
        if not self.messages:
            return ""
        last = self.messages[-1]
        if last.role != "user":
            return ""
        chunks: list[str] = []
        for raw in last.parts:
            if raw.get("type") != "text":
                continue
            text = raw.get("text")
            if isinstance(text, str):
                chunks.append(text)
        return "".join(chunks)

    @property
    def last_user_message_id(self) -> UUID:
        """Use the last user message's id when it parses as a UUID; else fall back."""
        if self.messages:
            last = self.messages[-1]
            if last.role == "user":
                try:
                    return UUID(last.id)
                except ValueError:
                    pass
        return self.user_message_id


# ──────────────────────────── entry point ────────────────────────────


async def dispatch(
    *,
    body: ChatRequestBody,
    session: AsyncSession,
    user_id: UUID,
    compiled_graph: Any,
    memory_store: AsyncPostgresStore | None,
) -> Response:
    """Validate, persist, and start the v6 UIMessage stream for one turn."""
    await _ensure_chat_row(
        session,
        body.conversation_id,
        user_id=user_id,
        site_id=body.site_id,
        experiment_id=body.experiment_id,
    )
    await _persist_user_message(session, body)
    await session.commit()

    conversation = await ConversationRepository(session).get_by_id(body.conversation_id)
    effective_site_id = resolve_site_id(
        chat_site_id=conversation.site_id if conversation is not None else None,
        body_site_id=body.site_id,
        conversation_id=body.conversation_id,
    )
    body = body.model_copy(update={"site_id": effective_site_id})
    runtime_context = _build_runtime_context(
        conversation=conversation,
        site_id=effective_site_id,
        user_id=user_id,
        memory_store=memory_store,
    )

    return StreamingResponse(
        _event_source(
            incoming=body,
            user_id=user_id,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
        ),
        media_type="text/event-stream",
        headers=dict(VERCEL_AI_DSP_HEADERS),
    )


# ──────────────────── chat row + user message persistence ────────────────────


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
    state = PipelineState(
        conversation_id=incoming.conversation_id,
        user_id=user_id,
        site_id=incoming.site_id,
        mode=incoming.mode,
        user_message_id=user_message_id,
        user_prompt=user_text,
        user_parts=[{"type": "text", "text": user_text}],
        turn_trace_id=str(uuid4()),
        turn_created_at=datetime.now(UTC).isoformat(),
        turn_message_id=turn_message_id,
    )
    turn_meta = state.model_dump()
    turn_meta["supervisor_call_count"] = 0
    turn_meta["phase_call_counts"] = {}
    turn_meta["current_phase"] = None
    turn_meta["last_routing_reason"] = None
    turn_meta["last_assistant_prose"] = ""
    turn_meta["last_phase_outcome"] = None
    turn_meta["last_verification_message_id"] = None
    turn_meta["turn_message_parts"] = []
    return turn_meta


# ──────────────────── v6 chunk encoding ────────────────────


def _encode_chunk_dict(chunk: dict[str, Any]) -> str:
    """Encode a pre-serialized v6 chunk as one SSE frame."""
    return f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"


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


# ──────────────────── interrupt handling ────────────────────


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


# ──────────────────── turn stream orchestration ────────────────────


def _build_thread_config(incoming: ChatRequestBody) -> RunnableConfig:
    configurable: dict[str, Any] = {"thread_id": str(incoming.conversation_id)}
    return {
        "configurable": configurable,
        "metadata": {
            "turn_id": str(incoming.last_user_message_id),
            "user_prompt_preview": incoming.last_user_text[:120],
        },
    }


async def _iter_graph_chunks(
    *,
    incoming: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
    title_task: asyncio.Task[str] | None,
    turn_message_id: UUID,
) -> AsyncIterator[dict[str, Any]]:
    """Yield v6 chunk dicts for one graph turn."""
    thread_config = _build_thread_config(incoming)
    title_emitted = False
    graph_input = _build_turn_input(
        incoming, user_id, turn_message_id=turn_message_id,
    )

    async for mode, payload in compiled_graph.astream(
        graph_input,
        config=thread_config,
        context=runtime_context,
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom":
            chunk = _extract_chunk(payload)
            if chunk is not None:
                yield chunk
            if not title_emitted:
                async for title_chunk in _maybe_emit_title_chunk(
                    title_task=title_task,
                    conversation_id=incoming.conversation_id,
                    wait_for_completion=False,
                ):
                    yield title_chunk
                    title_emitted = True
        elif mode == "updates":
            for interrupt_chunk in _interrupt_chunks(payload):
                yield interrupt_chunk

    if not title_emitted:
        async for title_chunk in _maybe_emit_title_chunk(
            title_task=title_task,
            conversation_id=incoming.conversation_id,
            wait_for_completion=True,
        ):
            yield title_chunk


# ──────────────────── SSE event source ────────────────────


async def _event_source(
    *,
    incoming: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
) -> AsyncIterator[str]:
    """Drive the graph and bracket the turn with the v6 Start/Finish/Done chunks."""
    title_task = _maybe_start_title_task(incoming)
    cancelled = False
    saw_interrupt = False
    encountered_error = False

    turn_message_id = uuid4()
    start_chunk = StartChunk(message_id=str(turn_message_id))
    yield _encode_chunk_dict(
        start_chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
    )

    try:
        async for chunk in _iter_graph_chunks(
            incoming=incoming,
            user_id=user_id,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
            title_task=title_task,
            turn_message_id=turn_message_id,
        ):
            if chunk.get("type") == "data-background-task-started":
                saw_interrupt = True
            yield _encode_chunk_dict(chunk)
    except asyncio.CancelledError:
        runtime_context.cancel_event.set()
        logger.info("Conversation stream cancelled by client disconnect")
        cancelled = True
    except Exception as exc:
        runtime_context.cancel_event.set()
        encountered_error = True
        logger.exception(
            "Pipeline dispatcher failed",
            conversation_id=str(incoming.conversation_id),
            user_id=str(user_id),
            site_id=incoming.site_id,
            mode=incoming.mode,
            error_type=type(exc).__name__,
        )
        err = ErrorChunk(error_text=f"{type(exc).__name__}: {exc}")
        yield _encode_chunk_dict(
            err.model_dump(by_alias=True, mode="json", exclude_none=True),
        )
    finally:
        if not cancelled:
            finish_reason = _resolve_finish_reason(
                saw_interrupt=saw_interrupt,
                encountered_error=encountered_error,
            )
            finish = FinishChunk(finish_reason=finish_reason)
            yield _encode_chunk_dict(
                finish.model_dump(
                    by_alias=True, mode="json", exclude_none=True,
                ),
            )
            done = DoneChunk()
            yield _encode_chunk_dict(
                done.model_dump(by_alias=True, mode="json", exclude_none=True),
            )


def _resolve_finish_reason(
    *, saw_interrupt: bool, encountered_error: bool,
) -> Literal["stop", "error", "other"]:
    if encountered_error:
        return "error"
    if saw_interrupt:
        return "other"
    return "stop"


# ──────────────────── title generation (data-conversation-title) ────────────────────


def _maybe_start_title_task(
    incoming: ChatRequestBody,
) -> asyncio.Task[str] | None:
    prompt = incoming.last_user_text.strip()
    if not prompt:
        return None
    return asyncio.create_task(generate_conversation_title(prompt))


async def _maybe_emit_title_chunk(
    *,
    title_task: asyncio.Task[str] | None,
    conversation_id: UUID,
    wait_for_completion: bool,
) -> AsyncIterator[dict[str, Any]]:
    if title_task is None:
        return
    if not wait_for_completion and not title_task.done():
        return

    try:
        title = await title_task
    except Exception:
        logger.exception("Conversation title generation failed")
        return
    if not title:
        return

    async with async_session_factory() as session:
        conv_repo = ConversationRepository(session)
        conversation = await conv_repo.get_by_id(conversation_id)
        if conversation is not None and conversation.name:
            return
        await conv_repo.update_conversation(conversation_id, ConversationUpdate(name=title))
        await session.commit()

    yield conversation_title_event(title=title).model_dump(
        by_alias=True, mode="json", exclude_none=True,
    )


__all__ = ["ChatRequestBody", "dispatch"]
