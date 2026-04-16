from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Interrupt
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from shared_py.stream_events import (
    CheckpointEvent,
    CustomEvent,
    DoneEvent,
    ErrorEvent,
    InterruptPayload,
    InterruptsEvent,
    StreamEvent,
    UpdatesEvent,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response, StreamingResponse

from pathfinder.ai.chat.title_generator import generate_conversation_title
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import background_task_started_event
from pathfinder.domain.strategy.plan_payload import (
    PersistedStrategyGraph,
    StrategyPlanPayload,
)
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import ChatRepository, MessagesRepository
from pathfinder.persistence.repositories.chat import ChatUpdate
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)

_SSE_EVENT_NAME: str = "stream"

DoneReason = Literal["completed", "interrupted", "error"]


class ChatRequestBody(CamelModel):
    """Typed body for ``POST /api/v1/chat`` — surfaces in OpenAPI as-is.

    The authenticated user UUID comes from the ``pathfinder-auth`` cookie
    (enforced by the ``CurrentUser`` dependency) — never from the body.
    Any ``userId`` the client sends is discarded by ``extra="ignore"`` so a
    forged body cannot act on behalf of a different account.
    """

    model_config = ConfigDict(extra="ignore")

    chat_id: UUID
    message: str
    parent_checkpoint_id: str | None = None
    site_id: str = ""
    mode: str = "strategy"
    experiment_id: str | None = None
    user_message_id: UUID = Field(default_factory=uuid4)


async def dispatch(
    *,
    body: ChatRequestBody,
    session: AsyncSession,
    user_id: UUID,
    compiled_graph: Any,
    memory_store: AsyncPostgresStore | None,
) -> Response:
    """Validate, persist, and start the SSE stream for one chat turn."""
    await _ensure_chat_row(
        session,
        body.chat_id,
        user_id=user_id,
        site_id=body.site_id,
        experiment_id=body.experiment_id,
    )
    await _persist_user_message(session, body)
    await session.commit()

    chat = await ChatRepository(session).get_by_id(body.chat_id)
    runtime_context = _build_runtime_context(
        chat=chat,
        site_id=body.site_id,
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
    )


async def _ensure_chat_row(
    session: AsyncSession,
    chat_id: UUID,
    *,
    user_id: UUID,
    site_id: str,
    experiment_id: str | None,
) -> None:
    existing = await session.get(Chat, chat_id)
    if existing is None:
        session.add(
            Chat(
                id=chat_id,
                user_id=user_id,
                site_id=site_id,
                name="",
                experiment_id=experiment_id,
            )
        )
        await session.flush()
        return
    if experiment_id and existing.experiment_id != experiment_id:
        existing.experiment_id = experiment_id
        await session.flush()


async def _persist_user_message(
    session: AsyncSession, incoming: ChatRequestBody
) -> None:
    repo = MessagesRepository(session)
    user_part = {"type": "text", "text": incoming.message}
    await repo.insert_message(
        message_id=incoming.user_message_id,
        chat_id=incoming.chat_id,
        role="user",
        parts=[user_part],
        metadata={"siteId": incoming.site_id, "mode": incoming.mode},
    )


def _build_runtime_context(
    *,
    chat: Chat | None,
    site_id: str,
    user_id: UUID,
    memory_store: AsyncPostgresStore | None,
) -> Context:
    persisted: PersistedStrategyGraph | None = None
    experiment_id: str | None = None
    if chat is not None:
        plan_payload: StrategyPlanPayload | None = None
        if chat.plan and "root" in chat.plan:
            try:
                plan_payload = StrategyPlanPayload.model_validate(chat.plan)
            except (ValueError, KeyError, TypeError):
                plan_payload = None
        persisted = PersistedStrategyGraph(
            id=str(chat.id),
            name=chat.name,
            plan=plan_payload,
            wdk_strategy_id=chat.wdk_strategy_id,
        )
        experiment_id = chat.experiment_id

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


def _build_turn_input(incoming: ChatRequestBody, user_id: UUID) -> dict[str, Any]:
    state = PipelineState(
        chat_id=incoming.chat_id,
        user_id=user_id,
        site_id=incoming.site_id,
        mode=incoming.mode,
        user_message_id=incoming.user_message_id,
        user_prompt=incoming.message,
        user_parts=[{"type": "text", "text": incoming.message}],
        turn_trace_id=str(uuid4()),
        turn_created_at=datetime.now(UTC).isoformat(),
    )
    turn_meta = state.model_dump()
    turn_meta["supervisor_call_count"] = 0
    turn_meta["phase_call_counts"] = {}
    turn_meta["current_phase"] = None
    turn_meta["last_routing_reason"] = None
    turn_meta["last_assistant_prose"] = ""
    turn_meta["last_verification_message_id"] = None
    return turn_meta


_STREAM_EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)


def _encode_event(event: StreamEvent) -> str:
    """Serialize a typed StreamEvent as one SSE frame.

    Frame format is fixed at ``event: stream\\ndata: {...camelCase JSON}\\n\\n``;
    the frontend parser filters on ``event: stream`` and drops everything else
    (heartbeats, comment frames). Every frame carries exactly one validated
    ``StreamEvent`` instance — no raw dicts, no manual JSON construction.
    """
    return (
        f"event: {_SSE_EVENT_NAME}\n"
        f"data: {event.model_dump_json(by_alias=True)}\n\n"
    )


class _StreamEventEnvelope(BaseModel):
    stream_event: dict[str, Any]


def _extract_stream_event(payload: object) -> StreamEvent | None:
    """Pull a ``StreamEvent`` out of the ``{"stream_event": {...}}`` writer envelope.

    Nodes emit via ``writer({"stream_event": event.model_dump(by_alias=True)})``.
    Anything not matching that envelope shape (e.g. raw control payloads from
    LangGraph internals routed via custom mode) is dropped silently.
    """
    if not isinstance(payload, dict):
        return None
    try:
        envelope = _StreamEventEnvelope.model_validate(payload)
    except ValidationError:
        return None
    return _STREAM_EVENT_ADAPTER.validate_python(envelope.stream_event)


_INTERRUPT_KEY: str = "__interrupt__"


def _emit_updates(payload: object) -> Iterator[StreamEvent]:
    """Yield one ``UpdatesEvent`` per node-write batch from a ``stream_mode='updates'`` payload.

    LangGraph emits ``{<node_name>: <writes>}`` per super-step. The
    ``__interrupt__`` key is special: callers handle it via
    :func:`_emit_interrupt_events`, so we skip it here.
    """
    if not isinstance(payload, dict):
        return
    for node, writes in payload.items():
        if node == _INTERRUPT_KEY:
            continue
        if not isinstance(writes, dict):
            continue
        yield UpdatesEvent(node=node, writes=writes)


class _DebugCheckpointConfigurable(BaseModel):
    model_config = ConfigDict(extra="ignore")

    checkpoint_id: str | None = None


class _DebugCheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    configurable: _DebugCheckpointConfigurable = Field(
        default_factory=_DebugCheckpointConfigurable,
    )


class _DebugCheckpointPayload(BaseModel):
    """Inner ``payload`` of a ``stream_mode='debug'`` checkpoint event.

    LangGraph emits ``{"type": "checkpoint", "step": int, "timestamp": str,
    "payload": {config, parent_config, values, metadata, next, tasks}}``.
    We only need the configs and ``next`` here (``next`` is the list of nodes
    scheduled to fire after this checkpoint).
    """

    model_config = ConfigDict(extra="ignore")

    config: _DebugCheckpointConfig = Field(default_factory=_DebugCheckpointConfig)
    parent_config: _DebugCheckpointConfig | None = None
    next: list[str] = Field(default_factory=list)


class _DebugEnvelope(BaseModel):
    """Envelope LangGraph wraps every debug-mode event in.

    ``type`` is one of ``checkpoint`` / ``task`` / ``task_result``; we only
    re-emit the ``checkpoint`` variant.
    """

    model_config = ConfigDict(extra="ignore")

    type: str
    step: int = 0
    timestamp: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


def _emit_debug(payload: object) -> Iterator[StreamEvent]:
    """Yield ``CheckpointEvent`` for each debug-mode ``type=='checkpoint'`` payload."""
    if not isinstance(payload, dict):
        return
    try:
        envelope = _DebugEnvelope.model_validate(payload)
    except ValidationError:
        return
    if envelope.type != "checkpoint":
        return
    inner = _DebugCheckpointPayload.model_validate(envelope.payload)
    checkpoint_id = inner.config.configurable.checkpoint_id
    if checkpoint_id is None:
        # The very first debug emission (input step) lacks a checkpoint id.
        return
    parent_id = (
        inner.parent_config.configurable.checkpoint_id
        if inner.parent_config is not None
        else None
    )
    next_node = inner.next[0] if inner.next else None
    yield CheckpointEvent(
        checkpoint_id=checkpoint_id,
        parent_checkpoint_id=parent_id,
        node=next_node,
        step=envelope.step,
        created_at=envelope.timestamp,
    )


async def _stream_graph_chunks(
    *,
    incoming: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
    title_task: asyncio.Task[str] | None,
) -> AsyncIterator[str]:
    """Yield SSE-encoded frames for the lifetime of one graph turn.

    Returns SSE strings for every typed event ``_iter_stream_events`` yields,
    so the outer ``_event_source`` only owns DoneEvent emission, error
    handling, and cancellation. The inner generator owns event synthesis.
    """
    async for event in _iter_stream_events(
        incoming=incoming,
        user_id=user_id,
        compiled_graph=compiled_graph,
        runtime_context=runtime_context,
        title_task=title_task,
    ):
        yield _encode_event(event)


def _build_thread_config(incoming: ChatRequestBody) -> RunnableConfig:
    """Compose the LangGraph ``RunnableConfig`` for one chat turn.

    When ``parent_checkpoint_id`` is present and points at a non-leaf
    checkpoint, LangGraph automatically forks a branched child checkpoint
    rather than appending to the leaf. The dispatcher does no extra work
    beyond setting the ``checkpoint_id`` key.
    """
    configurable: dict[str, Any] = {"thread_id": str(incoming.chat_id)}
    if incoming.parent_checkpoint_id:
        configurable["checkpoint_id"] = incoming.parent_checkpoint_id
    return {
        "configurable": configurable,
        "metadata": {
            "turn_id": str(incoming.user_message_id),
            "user_prompt_preview": incoming.message[:120],
        },
    }


async def _iter_stream_events(
    *,
    incoming: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
    title_task: asyncio.Task[str] | None,
) -> AsyncIterator[StreamEvent]:
    """Stream typed ``StreamEvent`` instances for one graph turn.

    Multiplexes all four LangGraph stream modes:

    - ``custom``: pass-through of the ``{"stream_event": ...}`` envelope our
      nodes emit via :class:`LangGraphEventAdapter`.
    - ``updates``: synthesize :class:`UpdatesEvent` per node-write batch and
      detect ``__interrupt__`` writes.
    - ``debug``: re-emit each checkpoint event as :class:`CheckpointEvent`.
    - ``messages``: explicitly ignored to avoid double-streaming the deltas
      our ``custom``-mode adapter already produces.
    """
    thread_config = _build_thread_config(incoming)
    title_emitted = False
    graph_input = _build_turn_input(incoming, user_id)

    async for mode, payload in compiled_graph.astream(
        graph_input,
        config=thread_config,
        context=runtime_context,
        stream_mode=["custom", "updates", "messages", "debug"],
    ):
        async for event in _events_for_mode(mode, payload):
            yield event
        if mode == "custom" and not title_emitted:
            async for title_event in _maybe_emit_title_metadata(
                title_task=title_task,
                chat_id=incoming.chat_id,
                wait_for_completion=False,
            ):
                yield title_event
                title_emitted = True

    if not title_emitted:
        async for title_event in _maybe_emit_title_metadata(
            title_task=title_task,
            chat_id=incoming.chat_id,
            wait_for_completion=True,
        ):
            yield title_event


async def _events_for_mode(
    mode: str, payload: object,
) -> AsyncIterator[StreamEvent]:
    """Synthesize StreamEvents for one LangGraph stream-mode tuple."""
    if mode == "custom":
        event = _extract_stream_event(payload)
        if event is not None:
            yield event
    elif mode == "updates":
        for interrupt_event in _interrupt_events(payload):
            yield interrupt_event
        for update_event in _emit_updates(payload):
            yield update_event
    elif mode == "debug":
        for ckpt_event in _emit_debug(payload):
            yield ckpt_event
    # mode == "messages" intentionally dropped — see ``_iter_stream_events``.


class _DurableInterruptPayload(BaseModel):
    """Typed shape of the value passed to ``interrupt()`` by ``@durable_tool``."""

    kind: Literal["durable_task"]
    task_id: str
    tool_name: str
    estimated_duration_seconds: int


def _interrupt_events(payload: object) -> Iterator[StreamEvent]:
    """Yield typed StreamEvents for each ``__interrupt__`` entry in an updates payload.

    Emits one :class:`InterruptsEvent` for the whole batch, then one
    :class:`CustomEvent` of kind ``data-background-task-started`` per parsed
    durable interrupt — the frontend uses the latter to render task cards.
    """
    raw = _iter_raw_interrupts(payload)
    durables = [d for _, d in raw]
    if not durables:
        return
    yield InterruptsEvent(
        interrupts=[
            InterruptPayload(
                id=interrupt_obj.id,
                value=durable.model_dump(mode="json"),
            )
            for interrupt_obj, durable in raw
        ]
    )
    for durable in durables:
        yield background_task_started_event(
            task_id=UUID(durable.task_id),
            tool_name=durable.tool_name,
            estimated_duration_seconds=durable.estimated_duration_seconds,
        )


async def _emit_interrupt_events(payload: object) -> AsyncIterator[str]:
    """Async-iter shim around :func:`_interrupt_events` retained for tests.

    The interrupt integration test exercises the dispatcher's interrupt
    pathway against a real graph; keeping this shim lets the test stay free
    of stream-mode plumbing while the core synthesis runs through the typed
    :func:`_interrupt_events` generator used by the real dispatch loop.
    """
    for event in _interrupt_events(payload):
        yield _encode_event(event)


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
                item.value, strict=False
            )
        except ValidationError:
            continue
        parsed.append((item, durable))
    return parsed


async def _event_source(
    *,
    incoming: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
) -> AsyncIterator[str]:
    """Drive the typed-event stream and bracket it with one terminal DoneEvent.

    Yields SSE-encoded frames until the inner generator completes or raises;
    on error emits an :class:`ErrorEvent` first, on cancellation emits
    nothing extra (the client disconnected). The ``finally`` block always
    emits exactly one terminal :class:`DoneEvent` whose ``reason`` reflects
    completion / interrupt / error so clients have a single canonical
    end-of-stream marker.
    """
    title_task = _maybe_start_title_task(incoming)
    cancelled = False
    saw_interrupt = False
    encountered_error = False
    try:
        async for event in _iter_stream_events(
            incoming=incoming,
            user_id=user_id,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
            title_task=title_task,
        ):
            if isinstance(event, InterruptsEvent):
                saw_interrupt = True
            yield _encode_event(event)
    except asyncio.CancelledError:
        runtime_context.cancel_event.set()
        logger.info("Chat stream cancelled by client disconnect")
        cancelled = True
    except Exception as exc:
        runtime_context.cancel_event.set()
        encountered_error = True
        logger.exception(
            "Pipeline dispatcher failed",
            chat_id=str(incoming.chat_id),
            user_id=str(user_id),
            site_id=incoming.site_id,
            mode=incoming.mode,
            error_type=type(exc).__name__,
        )
        yield _encode_event(
            ErrorEvent(message=f"{type(exc).__name__}: {exc}")
        )
    finally:
        if not cancelled:
            reason = _resolve_done_reason(
                saw_interrupt=saw_interrupt,
                encountered_error=encountered_error,
            )
            yield _encode_event(DoneEvent(reason=reason))


def _resolve_done_reason(
    *, saw_interrupt: bool, encountered_error: bool
) -> DoneReason:
    if encountered_error:
        return "error"
    if saw_interrupt:
        return "interrupted"
    return "completed"


def _maybe_start_title_task(
    incoming: ChatRequestBody,
) -> asyncio.Task[str] | None:
    user_prompt = incoming.message.strip()
    if not user_prompt:
        return None
    return asyncio.create_task(generate_conversation_title(user_prompt))


async def _maybe_emit_title_metadata(
    *,
    title_task: asyncio.Task[str] | None,
    chat_id: UUID,
    wait_for_completion: bool,
) -> AsyncIterator[StreamEvent]:
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
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_id(chat_id)
        if chat is not None and chat.name:
            return
        await chat_repo.update_chat(chat_id, ChatUpdate(name=title))
        await session.commit()

    yield CustomEvent(kind="data-conversation-title", data={"title": title})


__all__ = ["ChatRequestBody", "dispatch"]
