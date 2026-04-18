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
import json as _json
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.tools.durable import TaskProgressEmitter
from pathfinder.jobs.registry import TOOL_REGISTRY
from pathfinder.jobs.runtime import build_worker_runtime_context
from pathfinder.persistence.models import ConversationEvent
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
) -> None:
    """Execute a durable tool impl on the worker and resume the graph."""
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
        async with lifespan_memory_store(settings.database_url) as raw_memory:
            mem_store = MemoryStore(store=raw_memory)
            base_context = await build_worker_runtime_context(
                conversation_id=thread_id, task_id=task_id
            )
            context = dataclasses.replace(base_context, memory_store=raw_memory)
            try:
                payload = await impl(
                    context=context,
                    task_id=task_uuid,
                    progress=progress,
                    memory_store=mem_store,
                    **args.get("kwargs", {}),
                )
            finally:
                # Flush any residual buffered progress rows before the impl's
                # outcome is recorded — clients must see the final steps.
                await progress.aclose()
    except Exception as exc:  # worker must record every failure
        logger.exception("durable tool failed", tool_name=tool_name)
        error = str(exc) or exc.__class__.__name__
        await repo.mark_failed(task_id=task_uuid, error=error)
        await _safe_resume_graph_with_error(thread_id, task_uuid, error)
        return

    result = _to_dict(payload)
    await repo.mark_result_ready(task_id=task_uuid, result=result)
    await repo.mark_resuming(task_id=task_uuid)
    resume_error = await _safe_resume_graph_with_result(
        thread_id, task_uuid, result,
    )
    if resume_error is None:
        await repo.mark_complete(task_id=task_uuid)
    else:
        await repo.mark_failed(task_id=task_uuid, error=resume_error)


async def _safe_resume_graph_with_result(
    thread_id: str, task_id: UUID, result: dict[str, Any],
) -> str | None:
    """Resume the graph. Returns ``None`` on success or an error string.

    The error string includes the exception class + message so the user
    sees something actionable on ``background_tasks.error`` rather than
    "something went wrong".
    """
    try:
        await _resume_graph_with_result(thread_id, task_id, result)
    except Exception as exc:
        logger.exception(
            "graph resume with result failed",
            thread_id=thread_id, task_id=str(task_id),
        )
        return f"resume failed: {exc.__class__.__name__}: {exc}"
    return None


async def _safe_resume_graph_with_error(
    thread_id: str, task_id: UUID, error: str,
) -> None:
    try:
        await _resume_graph_with_error(thread_id, task_id, error)
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
    thread_id: str, task_id: UUID, result: dict[str, Any]
) -> None:
    await _resume_graph(
        thread_id=thread_id,
        task_id=task_id,
        resume_value={"status": "success", "result": result},
    )


async def _resume_graph_with_error(
    thread_id: str, task_id: UUID, error: str
) -> None:
    await _resume_graph(
        thread_id=thread_id,
        task_id=task_id,
        resume_value={"status": "failed", "error": error},
    )


async def _resume_graph(
    *,
    thread_id: str,
    task_id: UUID,
    resume_value: dict[str, Any],
) -> None:
    settings = get_settings()
    async with (
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
        async for mode, chunk_payload in graph.astream(
            Command(resume=resume_value),
            config=config,
            context=context,
            stream_mode=["custom"],
        ):
            if mode != "custom":
                continue
            sse = _extract_sse(chunk_payload)
            if sse is None:
                continue
            await _persist_chat_event(
                conversation_id=UUID(thread_id), task_id=task_id, chunk={"sse": sse}
            )


class _ResumedChunkEnvelope(BaseModel):
    chunk: dict[str, Any]


def _extract_sse(payload: Any) -> str | None:
    """Re-encode a resumed-graph custom payload as an AI SDK v6 SSE frame.

    Node writers emit the ``{"chunk": <v6_chunk_dict>}`` envelope; we
    re-serialise each chunk as ``data: {json}\\n\\n`` so the persisted
    ``chat_events.chunk`` rows match the live dispatcher's v6 wire format.
    """
    if not isinstance(payload, dict):
        return None
    try:
        envelope = _ResumedChunkEnvelope.model_validate(payload)
    except ValidationError:
        return None
    return f"data: {_json.dumps(envelope.chunk, separators=(',', ':'))}\n\n"


async def _persist_chat_event(
    *, conversation_id: UUID, task_id: UUID, chunk: dict[str, Any]
) -> None:
    """Persist an SSE chunk + NOTIFY listeners on ``chat_events:<conversation_id>``."""
    async with async_session_factory() as session:
        row = ConversationEvent(conversation_id=conversation_id, task_id=task_id, chunk=chunk)
        session.add(row)
        await session.flush()
        await session.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {
                "channel": f"chat_events:{conversation_id}",
                "payload": str(task_id),
            },
        )
        await session.commit()
