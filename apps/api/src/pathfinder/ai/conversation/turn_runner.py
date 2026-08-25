from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from assistant_core.conversation.event_writer import ChatWriter
from assistant_core.graph.stream_events import (
    conversation_title_event,
    turn_failed_event,
    turn_status_event,
    turn_stopped_event,
)
from assistant_core.mcp.admission import AdmissionRecord
from assistant_core.mcp.resolution import (
    ResolvedToolSources,
    ToolSourceUnavailableError,
)
from assistant_core.platform.db import async_session_factory
from assistant_core.platform.logging import get_logger
from assistant_core.spec import (
    AssistantSpec,
    TurnContextRequest,
    turn_input,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    StartChunk,
)

from pathfinder.ai.conversation._turn_helpers import (
    _extract_chunk,
    _interrupt_chunks,
    build_turn_start,
    resolve_site_id,
)
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.title_generator import generate_conversation_title
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    ConversationRepository,
)
from pathfinder.persistence.repositories.conversation_update import (
    ConversationUpdate,
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
    spec: AssistantSpec,
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
    async with contextlib.AsyncExitStack() as tool_source_sessions:
        tool_sources: dict[str, Any] = {}
        if spec.tool_sources:
            resolved = await tool_source_sessions.enter_async_context(
                ResolvedToolSources(
                    declarations=spec.tool_sources,
                    credential=deployment_credential,
                ),
            )
            tool_sources = dict(resolved.by_name)
        runtime_context = await spec.build_turn_context(
            TurnContextRequest(
                conversation=conversation,
                site_id=effective_site_id,
                user_id=user_id,
                memory_store=memory_store,
                cancel_event=asyncio.Event(),
                phase_models=body.runtime_phase_models,
                phase_reasoning=body.runtime_phase_reasoning,
                tool_sources=tool_sources,
            ),
        )
        await _run_turn_with_context(
            body=body,
            user_id=user_id,
            spec=spec,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
            writer=writer,
        )


def deployment_credential(record: AdmissionRecord) -> str | None:
    """Refuse a credentialed source until a deployment configures one."""
    msg = f"no credential is configured for tool source {record.source_id!r}"
    raise ToolSourceUnavailableError(msg)


async def _run_turn_with_context(
    *,
    body: ChatRequestBody,
    user_id: UUID,
    spec: AssistantSpec,
    compiled_graph: Any,
    runtime_context: Any,
    writer: ChatWriter,
) -> None:
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
            generate_conversation_title(body.last_user_text, spec.build_mock_model),
        )

    graph_input = turn_input(
        spec.build_initial_state(
            build_turn_start(
                body,
                user_id,
                turn_message_id=writer.turn_id,
                turn_start_event_id=start_event_id - 1,
            ),
        ),
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
    if spec.turn_epilogue is not None:
        for chunk in await spec.turn_epilogue(body.conversation_id):
            await writer.write(chunk)
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
        error_text = f"{type(exc).__name__}: {exc}"
        for chunk in (
            ErrorChunk(error_text=error_text),
            turn_failed_event(error_text=error_text),
        ):
            await writer.write(
                chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
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
