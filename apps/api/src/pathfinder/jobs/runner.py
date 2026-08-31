"""Worker-side runner for durable tool invocations.

Called from Procrastinate tasks (see ``jobs/tasks.py``). Looks up the real
implementation in ``TOOL_REGISTRY``, builds a worker-side ``Context``,
executes the impl, persists the result on the ``background_tasks`` row, and
opens a NEW turn on the thread that answers the deferred call the tool left
parked. The turn's chunks are persisted to ``conversation_events``, so a UI
that reconnects after the original request disconnected replays them.
"""

from __future__ import annotations

import dataclasses
from contextlib import nullcontext
from typing import Any, Literal
from uuid import UUID

from assistant_core.conversation.checkpointer import lifespan_checkpointer
from assistant_core.conversation.event_writer import (
    ChatEventWriter,
    append_chunk,
)
from assistant_core.graph.stream_events import task_completed_event
from assistant_core.graph.turn_state import DurableTaskResult, PendingDurableCall
from assistant_core.memory.lifespan import lifespan_memory_store
from assistant_core.memory.store import MemoryStore
from assistant_core.platform.db import async_session_factory
from assistant_core.platform.logging import get_logger
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from pathfinder.ai.conversation.assistant_routing import resolve_assistant
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.turn_runner import TurnRequest, run_turn
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
from pathfinder.platform.context import PhaseOverrides
from pathfinder.services.conversations.authz import (
    conversation_assistant_id,
    conversation_owner_id,
)

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
    """Execute a durable tool impl on the worker and open the completion turn.

    The worker-to-worker procrastinate hop drops ``ContextVar`` state, so the
    dispatcher (``@durable_tool`` wrapper) serializes the VEuPathDB auth
    cookie into the task payload and we re-install it here for the impl's
    lifetime. Without this, any WDK call inside the impl (enrichment,
    control tests, optimization) would fall through to the service-account
    token in settings. ``capture_dir`` (devtools only) re-installs LLM capture
    so the completion turn, where the agent reads the result, is recorded.
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
        await _safe_completion_turn(
            thread_id,
            DurableTaskResult(task_id=task_uuid, status="failed", error=error),
            veupathdb_auth_token=veupathdb_auth_token,
        )
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
        await _safe_completion_turn(
            thread_id,
            DurableTaskResult(task_id=task_uuid, status="failed", error=error),
            veupathdb_auth_token=veupathdb_auth_token,
        )
        return

    result = _to_dict(payload)
    await repo.mark_result_ready(task_id=task_uuid, result=result)
    await repo.mark_resuming(task_id=task_uuid)
    await _announce_completion(chat_uuid, task_uuid, "success", None)
    turn_error = await _safe_completion_turn(
        thread_id,
        DurableTaskResult(task_id=task_uuid, status="success", result=result),
        veupathdb_auth_token=veupathdb_auth_token,
    )
    if turn_error is None:
        await repo.mark_complete(task_id=task_uuid)
    else:
        await repo.mark_failed(task_id=task_uuid, error=turn_error)


async def _announce_completion(
    conversation_id: UUID,
    task_id: UUID,
    status: Literal["success", "failed"],
    error: str | None,
) -> None:
    """Record the tool's outcome on the thread, before the completion turn.

    The status reports whether the tool produced a result. A completion turn
    that then fails reports its own failure.
    """
    await append_chunk(
        conversation_id=conversation_id,
        chunk=task_completed_event(
            task_id=task_id,
            status=status,
            error=error,
        ).model_dump(by_alias=True, mode="json", exclude_none=True),
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


async def _safe_completion_turn(
    thread_id: str,
    result: DurableTaskResult,
    *,
    veupathdb_auth_token: str | None = None,
) -> str | None:
    """Open the completion turn. Returns ``None`` on success or an error string.

    The error string includes the exception class + message so the user sees
    something actionable on ``background_tasks.error`` rather than
    "something went wrong".
    """
    try:
        await _run_completion_turn(
            thread_id=thread_id,
            result=result,
            veupathdb_auth_token=veupathdb_auth_token,
        )
    except Exception as exc:
        logger.exception(
            "durable completion turn failed",
            thread_id=thread_id,
            task_id=str(result.task_id),
        )
        return f"completion turn failed: {exc.__class__.__name__}: {exc}"
    return None


def _parked_turn_message_id(snapshot: Any) -> UUID:
    raw = snapshot.values.get("turn_message_id")
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        return UUID(raw)
    msg = "checkpoint snapshot missing turn_message_id"
    raise RuntimeError(msg)


def _parked_task_id(snapshot: Any) -> UUID | None:
    """The durable call the thread parked, when it still waits on one."""
    parked = snapshot.values.get("pending_durable_call")
    if parked is None:
        return None
    return PendingDurableCall.model_validate(parked).task_id


async def _completion_body(
    *,
    conversation_id: UUID,
    task_id: UUID,
) -> ChatRequestBody:
    """The request body the completion turn runs under.

    The picks are request-scoped and the request that made them is gone, so
    they are read back from the row the deferring turn wrote.
    """
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    task = await repo.get(task_id=task_id)
    overrides = PhaseOverrides.model_validate(
        {} if task is None else task.phase_overrides,
    )
    return ChatRequestBody.model_validate(
        {
            "conversation_id": conversation_id,
            "phase_models": overrides.models,
            "phase_reasoning": overrides.reasoning,
        },
    )


async def _run_completion_turn(
    *,
    thread_id: str,
    result: DurableTaskResult,
    veupathdb_auth_token: str | None = None,
) -> None:
    """Open a new turn that answers the durable call the thread parked.

    The turn carries the tool's result into the run that deferred it, so
    nothing before the call runs a second time. It writes through
    :class:`ChatEventWriter` under the parked turn's message id, so the
    answer patches the tool part the suspending turn left behind.
    """
    settings = get_settings()
    registry = get_assistant_registry()
    conversation_id = UUID(thread_id)
    assistant_id = await conversation_assistant_id(conversation_id)
    if assistant_id is None:
        logger.info("no conversation to answer", thread_id=thread_id)
        return
    spec = resolve_assistant(registry, assistant_id)
    async with (
        attach_wdk_auth(veupathdb_auth_token),
        attach_conversation_application(conversation_id),
        lifespan_checkpointer(
            settings.database_url,
            checkpoint_types=registry.checkpoint_types(),
        ) as saver,
        lifespan_memory_store(settings.database_url) as store,
    ):
        graph = spec.build_graph(saver)
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await graph.aget_state(config)
        if _parked_task_id(snapshot) != result.task_id:
            logger.info(
                "no parked durable call to answer",
                thread_id=thread_id,
                task_id=str(result.task_id),
            )
            return
        user_id = await conversation_owner_id(conversation_id)
        if user_id is None:
            logger.info("no owner to answer as", thread_id=thread_id)
            return
        writer = ChatEventWriter(
            conversation_id=conversation_id,
            turn_id=_parked_turn_message_id(snapshot),
        )
        body = await _completion_body(
            conversation_id=conversation_id,
            task_id=result.task_id,
        )
        async with attach_user_id(user_id):
            await run_turn(
                request=TurnRequest(
                    body=body,
                    user_id=user_id,
                    durable_result=result,
                ),
                spec=spec,
                compiled_graph=graph,
                memory_store=store,
                writer=writer,
            )
