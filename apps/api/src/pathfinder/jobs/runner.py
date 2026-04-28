"""Worker-side runner for durable tool invocations.

Called from Procrastinate tasks (see ``jobs/tasks.py``). Looks up the real
implementation in ``TOOL_REGISTRY``, builds a worker-side ``Context``,
executes the impl, persists the result on the ``background_tasks`` row, and
resumes the LangGraph with ``Command(resume=...)`` so the suspended phase
can produce its final output. Any SSE chunks emitted during resume are
persisted to ``chat_events`` so they can be replayed to a UI that reconnects
after the original request disconnected.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, ValidationError
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    FinishChunk,
    StartChunk,
)

from pathfinder.ai.conversation._turn_helpers import _interrupt_chunks
from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.tools.durable import TaskProgressEmitter
from pathfinder.jobs.auth_context import attach_user_id, attach_wdk_auth
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.jobs.runtime import build_worker_runtime_context
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def run_durable_task(
    *,
    tool_name: str,
    task_id: str,
    thread_id: str,
    args: dict[str, Any],
    veupathdb_auth_token: str | None = None,
) -> None:
    """Execute a durable tool impl on the worker and resume the graph.

    The worker→worker procrastinate hop drops ``ContextVar`` state, so the
    dispatcher (``@durable_tool`` wrapper) serializes the VEuPathDB auth
    cookie into the task payload and we re-install it here for the impl's
    lifetime. Without this, any WDK call inside the impl (enrichment,
    control tests, optimization) would fall through to the service-account
    token in settings.
    """
    task_uuid = UUID(task_id)
    chat_uuid = UUID(thread_id)
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_running(task_id=task_uuid)

    impl = TOOL_REGISTRY.get(tool_name)
    if impl is None:
        error = f"unknown durable tool: {tool_name}"
        logger.error("durable runner missing impl", tool_name=tool_name)
        await repo.mark_failed(task_id=task_uuid, error=error)
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
        await _safe_resume_graph_with_error(
            thread_id, task_uuid, error,
            veupathdb_auth_token=veupathdb_auth_token,
        )
        return

    result = _to_dict(payload)
    await repo.mark_result_ready(task_id=task_uuid, result=result)
    await repo.mark_resuming(task_id=task_uuid)
    resume_error = await _safe_resume_graph_with_result(
        thread_id, task_uuid, result, veupathdb_auth_token=veupathdb_auth_token,
    )
    if resume_error is None:
        await repo.mark_complete(task_id=task_uuid)
    else:
        await repo.mark_failed(task_id=task_uuid, error=resume_error)


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
            thread_id, task_id, result,
            veupathdb_auth_token=veupathdb_auth_token,
        )
    except Exception as exc:
        logger.exception(
            "graph resume with result failed",
            thread_id=thread_id, task_id=str(task_id),
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
            thread_id, task_id, error,
            veupathdb_auth_token=veupathdb_auth_token,
        )
    except Exception:
        logger.exception(
            "graph resume with error failed",
            thread_id=thread_id, task_id=str(task_id),
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
    replays — the resumed assistant message appears inline as a fresh bubble
    after the durable task completes. The earlier task-tagged sub-stream
    design hid every post-resume token from the chat.
    """
    settings = get_settings()
    async with (
        attach_wdk_auth(veupathdb_auth_token),
        lifespan_checkpointer(settings.database_url) as saver,
        lifespan_memory_store(settings.database_url) as raw_memory,
    ):
        graph = build_graph(checkpointer=saver)
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
        turn_id = uuid4()
        writer = ChatEventWriter(
            conversation_id=conversation_uuid, turn_id=turn_id,
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
                    thread_id=thread_id, task_id=str(task_id),
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


class _ResumedChunkEnvelope(BaseModel):
    chunk: dict[str, Any]


async def _emit_chunk(
    writer: ChatEventWriter,
    chunk: StartChunk | FinishChunk | DoneChunk,
) -> None:
    await writer.write(
        chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
    )


async def _emit_resume_custom(
    writer: ChatEventWriter, payload: Any,
) -> None:
    if not isinstance(payload, dict):
        return
    try:
        envelope = _ResumedChunkEnvelope.model_validate(payload)
    except ValidationError:
        return
    await writer.write(envelope.chunk)


