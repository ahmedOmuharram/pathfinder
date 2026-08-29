"""Worker-side runner for durable tool invocations.

Called from Procrastinate tasks (see ``jobs/tasks.py``). Looks up the real
implementation in ``TOOL_REGISTRY``, builds a worker-side ``Context``,
executes the impl, persists the result on the ``background_tasks`` row, and
resumes the LangGraph with ``Command(resume=...)`` so the suspended phase
can produce its final output. Any SSE chunks emitted during resume are
persisted to ``conversation_events`` so they can be replayed to a UI that
reconnects after the original request disconnected.
"""

from __future__ import annotations

import dataclasses
from contextlib import nullcontext
from typing import Any, Literal
from uuid import UUID

from assistant_core.conversation.checkpointer import lifespan_checkpointer
from assistant_core.conversation.event_writer import (
    ChatEventWriter,
    ChatWriter,
    append_chunk,
)
from assistant_core.graph.stream_events import task_completed_event
from assistant_core.memory.lifespan import lifespan_memory_store
from assistant_core.memory.store import MemoryStore
from assistant_core.platform.db import async_session_factory
from assistant_core.platform.logging import get_logger
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, ValidationError
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    FinishChunk,
    StartChunk,
)

from pathfinder.ai.conversation._turn_helpers import _interrupt_chunks
from pathfinder.ai.conversation.assistant_routing import resolve_assistant
from pathfinder.ai.graph._llm_capture import capture_llm
from pathfinder.assistants.registry import get_assistant_registry
from pathfinder.jobs.auth_context import (
    attach_conversation_application,
    attach_user_id,
    attach_wdk_auth,
)
from pathfinder.jobs.progress import TaskProgressEmitter
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.jobs.runtime import build_worker_runtime_context
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.platform.config import get_settings
from pathfinder.services.conversations.authz import conversation_assistant_id

logger = get_logger(__name__)


async def run_durable_task(
    *,
    tool_name: str,
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
    capture_dir: str | None = None,
) -> None:
    """Execute a durable tool impl on the worker and resume the graph.

    The worker-to-worker procrastinate hop drops ``ContextVar`` state, so the
    dispatcher (``@durable_tool`` wrapper) serializes the VEuPathDB auth
    cookie into the task payload and we re-install it here for the impl's
    lifetime. Without this, any WDK call inside the impl (enrichment,
    control tests, optimization) would fall through to the service-account
    token in settings. ``capture_dir`` (devtools only) re-installs LLM capture
    so the graph resume, where the post-result phase agent runs, is recorded.
    """
    capture = capture_llm(capture_dir) if capture_dir else nullcontext()
    with capture:
        await _run_durable_task_inner(
            tool_name=tool_name,
            task_id=task_id,
            thread_id=thread_id,
            args=args,
            veupathdb_auth_token=veupathdb_auth_token,
        )


async def _run_durable_task_inner(
    *,
    tool_name: str,
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    task_uuid = UUID(task_id)
    chat_uuid = UUID(thread_id)
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_running(task_id=task_uuid)

    impl = TOOL_REGISTRY.get(tool_name)
    if impl is None:
        error = f"unknown durable tool: {tool_name}"
        logger.error("durable runner missing impl", tool_name=tool_name)
        await repo.mark_failed(task_id=task_uuid, error=error)
        await _announce_completion(chat_uuid, task_uuid, "failed", error)
        await _resume_graph_with_error(thread_id, task_uuid, error)
        return

    progress = TaskProgressEmitter(
        task_id=task_uuid,
        conversation_id=chat_uuid,
        session_factory=async_session_factory,
    )

    settings = get_settings()
    try:
        async with (
            attach_wdk_auth(veupathdb_auth_token),
            attach_conversation_application(chat_uuid),
            lifespan_memory_store(settings.database_url) as raw_memory,
        ):
            mem_store = MemoryStore(store=raw_memory)
            base_context = await build_worker_runtime_context(
                conversation_id=thread_id, task_id=task_id
            )
            context = dataclasses.replace(base_context, memory_store=raw_memory)
            async with attach_user_id(context.user_id):
                try:
                    payload = await impl(
                        context=context,
                        task_id=task_uuid,
                        conversation_id=chat_uuid,
                        progress=progress,
                        memory_store=mem_store,
                        **args.get("kwargs", {}),
                    )
                finally:
                    await progress.aclose()
    except Exception as exc:  # worker must record every failure
        logger.exception("durable tool failed", tool_name=tool_name)
        error = str(exc) or exc.__class__.__name__
        await repo.mark_failed(task_id=task_uuid, error=error)
        await _announce_completion(chat_uuid, task_uuid, "failed", error)
        await _safe_resume_graph_with_error(
            thread_id,
            task_uuid,
            error,
            veupathdb_auth_token=veupathdb_auth_token,
        )
        return

    result = _to_dict(payload)
    await repo.mark_result_ready(task_id=task_uuid, result=result)
    await repo.mark_resuming(task_id=task_uuid)
    await _announce_completion(chat_uuid, task_uuid, "success", None)
    resume_error = await _safe_resume_graph_with_result(
        thread_id,
        task_uuid,
        result,
        veupathdb_auth_token=veupathdb_auth_token,
    )
    if resume_error is None:
        await repo.mark_complete(task_id=task_uuid)
    else:
        await repo.mark_failed(task_id=task_uuid, error=resume_error)


async def _announce_completion(
    conversation_id: UUID,
    task_id: UUID,
    status: Literal["success", "failed"],
    error: str | None,
) -> None:
    """Record the tool's outcome on the thread, before the graph resumes.

    The status reports whether the tool produced a result. A resume that then
    fails is reported by the resumed turn.
    """
    await append_chunk(
        conversation_id=conversation_id,
        chunk=task_completed_event(
            task_id=task_id,
            status=status,
            error=error,
        ).model_dump(by_alias=True, mode="json", exclude_none=True),
    )


async def _safe_resume_graph_with_result(
    thread_id: str,
    task_id: UUID,
    result: dict[str, Any],
    *,
    veupathdb_auth_token: str | None = None,
) -> str | None:
    """Resume the graph. Returns ``None`` on success or an error string.

    The error string includes the exception class + message so the user
    sees something actionable on ``background_tasks.error`` rather than
    "something went wrong".
    """
    try:
        await _resume_graph_with_result(
            thread_id,
            task_id,
            result,
            veupathdb_auth_token=veupathdb_auth_token,
        )
    except Exception as exc:
        logger.exception(
            "graph resume with result failed",
            thread_id=thread_id,
            task_id=str(task_id),
        )
        return f"resume failed: {exc.__class__.__name__}: {exc}"
    return None


async def _safe_resume_graph_with_error(
    thread_id: str,
    task_id: UUID,
    error: str,
    *,
    veupathdb_auth_token: str | None = None,
) -> None:
    try:
        await _resume_graph_with_error(
            thread_id,
            task_id,
            error,
            veupathdb_auth_token=veupathdb_auth_token,
        )
    except Exception:
        logger.exception(
            "graph resume with error failed",
            thread_id=thread_id,
            task_id=str(task_id),
        )


def _to_dict(value: Any) -> dict[str, Any]:
    """Coerce an impl's return into a JSON-serialisable dict.

    Impls return either a Pydantic ``BaseModel`` (dumped via alias + JSON
    mode) or a plain dict. Anything else is wrapped under ``value`` so the
    serialised row stays valid JSON.
    """
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


async def _resume_graph_with_result(
    thread_id: str,
    task_id: UUID,
    result: dict[str, Any],
    *,
    veupathdb_auth_token: str | None = None,
) -> None:
    await _resume_graph(
        thread_id=thread_id,
        task_id=task_id,
        resume_value={"status": "success", "result": result},
        veupathdb_auth_token=veupathdb_auth_token,
    )


async def _resume_graph_with_error(
    thread_id: str,
    task_id: UUID,
    error: str,
    *,
    veupathdb_auth_token: str | None = None,
) -> None:
    await _resume_graph(
        thread_id=thread_id,
        task_id=task_id,
        resume_value={"status": "failed", "error": error},
        veupathdb_auth_token=veupathdb_auth_token,
    )


async def _resume_graph(
    *,
    thread_id: str,
    task_id: UUID,
    resume_value: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    """Resume the suspended graph and stream the agent continuation back into
    the main chat.

    Output goes through :class:`ChatEventWriter` (no ``task_id`` tag) so it
    lands in the same ``conversation_events`` rows the chat dispatcher
    replays: the resumed assistant message appears inline as a fresh bubble
    after the durable task completes.
    """
    settings = get_settings()
    registry = get_assistant_registry()
    assistant_id = await conversation_assistant_id(UUID(thread_id))
    if assistant_id is None:
        logger.info("no conversation to resume", thread_id=thread_id)
        return
    spec = resolve_assistant(registry, assistant_id)
    async with (
        attach_wdk_auth(veupathdb_auth_token),
        attach_conversation_application(UUID(thread_id)),
        lifespan_checkpointer(
            settings.database_url,
            checkpoint_types=registry.checkpoint_types(),
        ) as saver,
        lifespan_memory_store(settings.database_url) as raw_memory,
    ):
        graph = spec.build_graph(saver)
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await graph.aget_state(config)
        if not snapshot.next:
            logger.info(
                "no pending graph state to resume",
                thread_id=thread_id,
                task_id=str(task_id),
            )
            return

        base_context = await build_worker_runtime_context(
            conversation_id=thread_id, task_id=str(task_id)
        )
        context = dataclasses.replace(base_context, memory_store=raw_memory)
        conversation_uuid = UUID(thread_id)
        turn_id = _resume_turn_message_id(snapshot)
        writer = ChatEventWriter(
            conversation_id=conversation_uuid,
            turn_id=turn_id,
        )
        await _emit_chunk(writer, StartChunk(message_id=str(turn_id)))
        encountered_error = False
        async with attach_user_id(context.user_id):
            try:
                async for mode, chunk_payload in graph.astream(
                    Command(resume=resume_value),
                    config=config,
                    context=context,
                    stream_mode=["custom", "updates"],
                ):
                    if mode == "custom":
                        await _emit_resume_custom(writer, chunk_payload)
                    elif mode == "updates":
                        for interrupt_chunk in _interrupt_chunks(chunk_payload):
                            await writer.write(interrupt_chunk)
            except Exception:
                encountered_error = True
                logger.exception(
                    "resume graph stream raised",
                    thread_id=thread_id,
                    task_id=str(task_id),
                )
                raise
            finally:
                await _emit_chunk(
                    writer,
                    FinishChunk(
                        finish_reason="error" if encountered_error else "stop",
                    ),
                )
                await _emit_chunk(writer, DoneChunk())


def _resume_turn_message_id(snapshot: Any) -> UUID:
    raw = snapshot.values.get("turn_message_id")
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        return UUID(raw)
    msg = "checkpoint snapshot missing turn_message_id"
    raise RuntimeError(msg)


class _ResumedChunkEnvelope(BaseModel):
    chunk: dict[str, Any]


async def _emit_chunk(
    writer: ChatWriter,
    chunk: StartChunk | FinishChunk | DoneChunk,
) -> None:
    await writer.write(
        chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
    )


async def _emit_resume_custom(
    writer: ChatWriter,
    payload: Any,
) -> None:
    if not isinstance(payload, dict):
        return
    try:
        envelope = _ResumedChunkEnvelope.model_validate(payload)
    except ValidationError:
        return
    await writer.write(envelope.chunk)
