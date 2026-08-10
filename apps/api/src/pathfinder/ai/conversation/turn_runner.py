from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    StartChunk,
)

from pathfinder.ai.conversation._turn_helpers import (
    _build_runtime_context,
    _build_turn_input,
    _extract_chunk,
    _interrupt_chunks,
    resolve_site_id,
)
from pathfinder.ai.conversation.event_writer import ChatWriter
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.title_generator import generate_conversation_title
from pathfinder.ai.graph.stream_events import (
    conversation_title_event,
    strategy_revision_event,
    turn_status_event,
    turn_stopped_event,
)
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    ConversationRepository,
)
from pathfinder.persistence.repositories.conversation import ConversationUpdate
from pathfinder.platform.db import async_session_factory
from pathfinder.platform.logging import get_logger
from pathfinder.services.conversations.responses import (
    conversation_strategy_revision,
)

_CANCEL_POLL_INTERVAL_SECONDS = 1.0

logger = get_logger(__name__)


@dataclass
class _DriveResult:
    saw_interrupt: bool = False
    encountered_error: bool = False
    title_emitted: bool = False
    cancelled: bool = False


@dataclass
class _StreamConsumerCtx:
    compiled_graph: Any
    graph_input: dict[str, Any]
    thread_config: dict[str, Any]
    runtime_context: Any
    title_task: asyncio.Task[str] | None
    body: ChatRequestBody
    writer: ChatWriter
    result: _DriveResult


async def _watch_for_cancel(
    *,
    conversation_id: UUID,
    turn_id: UUID,
    cancel_event: asyncio.Event,
) -> None:
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    while not cancel_event.is_set():
        try:
            cancelled = await repo.is_cancelled(
                conversation_id=conversation_id,
                turn_id=turn_id,
            )
        except Exception:
            logger.exception(
                "Cancel watcher poll failed",
                conversation_id=str(conversation_id),
                turn_id=str(turn_id),
            )
            return
        if cancelled:
            cancel_event.set()
            return
        try:
            await asyncio.sleep(_CANCEL_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return


async def run_turn(
    *,
    body: ChatRequestBody,
    user_id: UUID,
    compiled_graph: Any,
    memory_store: Any,
    writer: ChatWriter,
) -> None:
    """Drive one chat turn to completion, writing chunks through ``writer``.

    Runs to completion regardless of client state — no disconnect cancellation.
    The procrastinate worker that calls this coroutine is the owner; any client
    reattaches via the events SSE endpoint in a later task.
    """
    async with async_session_factory() as session:
        conversation = await ConversationRepository(session).get_by_id(
            body.conversation_id,
        )
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
        phase_models=body.phase_models,
        phase_reasoning=body.phase_reasoning,
    )

    turn_message_id = writer.turn_id
    start_event_id = await writer.write(
        StartChunk(message_id=str(turn_message_id)).model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        ),
    )
    await writer.write(
        turn_status_event(label="Preparing context").model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        ),
    )

    title_task: asyncio.Task[str] | None = None
    if body.last_user_text.strip():
        title_task = asyncio.create_task(
            generate_conversation_title(body.last_user_text),
        )

    graph_input = _build_turn_input(
        body,
        user_id,
        turn_message_id=writer.turn_id,
        turn_start_event_id=start_event_id - 1,
    )
    result = await _drive_graph(
        body=body,
        graph_input=graph_input,
        compiled_graph=compiled_graph,
        runtime_context=runtime_context,
        title_task=title_task,
        writer=writer,
    )

    if title_task is not None and not result.title_emitted:
        async for t in _emit_title(title_task, body.conversation_id):
            await writer.write(t)

    finish_reason = (
        "error"
        if result.encountered_error
        else "other"
        if result.saw_interrupt or result.cancelled
        else "stop"
    )
    if result.cancelled:
        await writer.write(
            turn_stopped_event().model_dump(
                by_alias=True,
                mode="json",
                exclude_none=True,
            ),
        )
    await _emit_strategy_revision(
        writer=writer,
        conversation_id=body.conversation_id,
    )
    await writer.write(
        FinishChunk(finish_reason=finish_reason).model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        ),
    )
    await writer.write(
        DoneChunk().model_dump(by_alias=True, mode="json", exclude_none=True),
    )


async def _emit_strategy_revision(
    *,
    writer: ChatWriter,
    conversation_id: UUID,
) -> None:
    """Stamp the finished turn with the strategy state it described.

    Read after the graph has run so it reflects any build this turn did.
    Nothing is emitted when the conversation has no strategy: a message that
    quoted no strategy counts can never be superseded by an edit to one.
    """
    async with async_session_factory() as session:
        conversation = await ConversationRepository(session).get_by_id(conversation_id)
    revision = conversation_strategy_revision(conversation)
    if not revision:
        return
    await writer.write(
        strategy_revision_event(revision=revision).model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        ),
    )


async def _consume_graph_stream(ctx: _StreamConsumerCtx) -> None:
    async for mode, payload in ctx.compiled_graph.astream(
        ctx.graph_input,
        config=ctx.thread_config,
        context=ctx.runtime_context,
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom":
            await _handle_custom(
                payload,
                ctx.title_task,
                ctx.body.conversation_id,
                ctx.result,
                ctx.writer,
            )
        elif mode == "updates":
            for interrupt_chunk in _interrupt_chunks(payload):
                ctx.result.saw_interrupt = True
                await ctx.writer.write(interrupt_chunk)


async def _drive_graph(
    *,
    body: ChatRequestBody,
    graph_input: dict[str, Any],
    compiled_graph: Any,
    runtime_context: Any,
    title_task: asyncio.Task[str] | None,
    writer: ChatWriter,
) -> _DriveResult:
    result = _DriveResult()
    turn_message_id: UUID = graph_input["turn_message_id"]
    thread_config = {
        "configurable": {"thread_id": str(body.conversation_id)},
        "metadata": {
            "turn_id": str(turn_message_id),
            "user_prompt_preview": body.last_user_text[:120],
        },
    }
    cancel_event: asyncio.Event = runtime_context.cancel_event

    consume_task = asyncio.create_task(
        _consume_graph_stream(
            _StreamConsumerCtx(
                compiled_graph=compiled_graph,
                graph_input=graph_input,
                thread_config=thread_config,
                runtime_context=runtime_context,
                title_task=title_task,
                body=body,
                writer=writer,
                result=result,
            ),
        ),
    )

    async def _kill_on_cancel() -> None:
        await cancel_event.wait()
        consume_task.cancel()

    cancel_watcher = asyncio.create_task(
        _watch_for_cancel(
            conversation_id=body.conversation_id,
            turn_id=turn_message_id,
            cancel_event=cancel_event,
        ),
    )
    killer = asyncio.create_task(_kill_on_cancel())
    try:
        await consume_task
    except asyncio.CancelledError:
        if cancel_event.is_set():
            result.cancelled = True
        else:
            raise
    except Exception as exc:
        result.encountered_error = True
        logger.exception(
            "Turn runner failed",
            conversation_id=str(body.conversation_id),
            user_id=str(graph_input.get("user_id")),
            error_type=type(exc).__name__,
        )
        await writer.write(
            ErrorChunk(error_text=f"{type(exc).__name__}: {exc}").model_dump(
                by_alias=True,
                mode="json",
                exclude_none=True,
            ),
        )
    finally:
        cancel_watcher.cancel()
        killer.cancel()
        for task in (cancel_watcher, killer):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
    return result


async def _handle_custom(
    payload: object,
    title_task: asyncio.Task[str] | None,
    conversation_id: UUID,
    result: _DriveResult,
    writer: ChatWriter,
) -> None:
    chunk = _extract_chunk(payload)
    if chunk is not None:
        await writer.write(chunk)
    if not result.title_emitted and title_task is not None and title_task.done():
        async for t in _emit_title(title_task, conversation_id):
            await writer.write(t)
            result.title_emitted = True


async def _emit_title(
    title_task: asyncio.Task[str],
    conversation_id: UUID,
) -> AsyncGenerator[dict[str, Any]]:
    try:
        title = await title_task
    except Exception:
        logger.exception("Conversation title generation failed")
        return
    if not title:
        return
    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        conversation = await repo.get_by_id(conversation_id)
        if conversation is not None and conversation.name:
            return
        await repo.update_conversation(
            conversation_id,
            ConversationUpdate(name=title),
        )
        await session.commit()
    yield conversation_title_event(title=title).model_dump(
        by_alias=True,
        mode="json",
        exclude_none=True,
    )
