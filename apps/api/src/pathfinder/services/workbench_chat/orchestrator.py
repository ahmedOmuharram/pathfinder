"""Workbench chat orchestration entrypoint (service layer).

Mirrors services/chat/orchestrator.py but scoped to experiment-bound
workbench conversations. Streams are keyed by (user_id, experiment_id)
instead of an explicit strategy UUID.

Uses a pydantic-ai Agent with WorkbenchDeps for tool injection.
The agent is built inline each turn (no pipeline/state machine needed).
"""

import asyncio
from uuid import uuid4

from pathfinder.platform.async_tasks import create_detached_task
from pathfinder.platform.events import emit
from pathfinder.platform.redis import get_redis
from pathfinder.services.chat.types import ChatContext
from pathfinder.services.workbench_chat.producer import (
    WorkbenchProducerIds,
    WorkbenchTurnConfig,
    workbench_chat_producer,
)

# Registry of running workbench chat tasks keyed by operation_id.
# Used to cancel operations from the HTTP layer.
_active_tasks: dict[str, asyncio.Task[None]] = {}


async def start_workbench_chat_stream(
    *,
    message: str,
    site_id: str,
    experiment_id: str,
    context: ChatContext,
    config: WorkbenchTurnConfig | None = None,
) -> tuple[str, str]:
    """Start a background workbench chat operation and return its identifiers.

    Returns ``(operation_id, stream_id)`` so the caller can hand them
    to the client. The client subscribes to
    ``GET /operations/{operation_id}/subscribe`` for SSE events.

    Only fast, essential work runs synchronously (user lookup, stream
    resolution, operation registration, user_message emission).
    All heavy lifting is deferred into the background producer.
    """
    cfg = config or WorkbenchTurnConfig()

    await context.user_repo.get_or_create(context.user_id)

    # Find existing stream for this experiment or create a new one.
    stream = await context.stream_repo.find_by_experiment(
        context.user_id, experiment_id
    )
    if stream is None:
        stream = await context.stream_repo.create(
            user_id=context.user_id,
            site_id=site_id,
            experiment_id=experiment_id,
        )

    stream_id_str = str(stream.id)
    operation_id = f"op_{uuid4().hex[:12]}"

    # Persist user message to Redis NOW (survives even if producer errors).
    redis = get_redis()
    await emit(
        redis,
        stream_id_str,
        operation_id,
        "user_message",
        {"content": message, "messageId": str(uuid4())},
        session=context.stream_repo.session,
    )

    # Register the operation in PostgreSQL for client discovery.
    await context.stream_repo.register_operation(
        operation_id, stream.id, "workbench_chat"
    )

    # Commit before launching the background producer — it creates its own
    # session and must be able to read the Stream/StreamProjection/Operation.
    await context.stream_repo.session.commit()

    ids = WorkbenchProducerIds(
        stream_id_str=stream_id_str,
        operation_id=operation_id,
        site_id=site_id,
        experiment_id=experiment_id,
        user_id=context.user_id,
    )

    # Launch the background producer as an asyncio task.
    task = create_detached_task(
        workbench_chat_producer(ids=ids, message=message, config=cfg),
        name=f"workbench-chat-producer:{operation_id}",
    )
    _active_tasks[operation_id] = task
    task.add_done_callback(lambda _: _active_tasks.pop(operation_id, None))

    return operation_id, stream_id_str


async def cancel_workbench_chat_operation(operation_id: str) -> bool:
    """Cancel a running workbench chat operation.

    Returns True if the operation was found and cancelled, False otherwise.
    """
    task = _active_tasks.get(operation_id)
    if task is None:
        return False
    task.cancel()
    return True
