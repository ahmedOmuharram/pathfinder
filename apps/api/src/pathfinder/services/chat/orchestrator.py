"""Chat orchestration entrypoint (service layer) — CQRS version.

Public API: ``configure``, ``start_chat_stream``, ``cancel_chat_operation``.

Every event is persisted to Redis the moment it's emitted. The PostgreSQL
projection is updated inline. No accumulation, no finalization step.

The pydantic-ai pipeline is invoked directly — no injected factory pattern.
"""

import asyncio
import contextlib
from collections.abc import Callable
from uuid import UUID, uuid4

from pathfinder.persistence.models import Stream
from pathfinder.persistence.repositories import StreamRepository
from pathfinder.platform.async_tasks import create_detached_task
from pathfinder.platform.context import operation_id_ctx, stream_id_ctx
from pathfinder.platform.errors import InternalError
from pathfinder.platform.event_schemas import PipelineConfig, UserMessageEventData
from pathfinder.platform.events import emit
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.services.chat.producer import chat_producer
from pathfinder.services.chat.types import (
    ChatContext,
    ChatTurnConfig,
    TurnIdentity,
)
from pathfinder.services.chat.utils import parse_selected_nodes

logger = get_logger(__name__)

# Registry of running chat tasks keyed by operation_id.
# Used to cancel operations from the HTTP layer.
_active_tasks: dict[str, asyncio.Task[None]] = {}

# ── Pipeline resolution ──────────────────────────────────────────
# Injected at startup via configure().

_resolve_pipeline_holder: dict[str, Callable[..., PipelineConfig]] = {}


def configure(
    *,
    resolve_pipeline_fn: Callable[..., PipelineConfig],
) -> None:
    """Wire pipeline resolution into the orchestrator.

    Called once at application startup from the composition root.
    """
    _resolve_pipeline_holder["v"] = resolve_pipeline_fn


async def _ensure_stream(
    stream_repo: StreamRepository,
    *,
    user_id: UUID,
    site_id: str,
    stream_id: UUID | None,
) -> Stream:
    """Ensure a stream exists, creating one if needed."""
    if stream_id:
        stream = await stream_repo.get_by_id(stream_id)
        if stream:
            return stream
        logger.warning("Stream not found; creating new", stream_id=stream_id)
        return await stream_repo.create(
            user_id=user_id, site_id=site_id, stream_id=stream_id
        )
    return await stream_repo.create(user_id=user_id, site_id=site_id)


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    context: ChatContext,
    config: ChatTurnConfig | None = None,
) -> tuple[str, str, str]:
    """Start a background chat operation and return its identifiers.

    Returns ``(operation_id, stream_id, entry_id)`` so the caller can
    hand them to the client. ``entry_id`` is the Redis stream entry ID
    of the ``user_message`` event — the frontend stores it for undo.

    Only fast, essential work runs synchronously (user lookup, stream
    resolution, operation registration, user_message emission).
    All heavy lifting is deferred into the background producer.
    """
    cfg = config or ChatTurnConfig()

    await context.user_repo.get_or_create(context.user_id)

    stream = await _ensure_stream(
        context.stream_repo,
        user_id=context.user_id,
        site_id=site_id,
        stream_id=strategy_id,
    )

    stream_id_str = str(stream.id)
    operation_id = f"op_{uuid4().hex[:12]}"

    # Persist user message to Redis NOW (survives even if producer errors).
    redis = get_redis()
    entry_id = await emit(
        redis,
        stream_id_str,
        operation_id,
        "user_message",
        UserMessageEventData(content=message, message_id=str(uuid4())).model_dump(
            by_alias=True, exclude_none=True
        ),
        session=context.stream_repo.session,
    )

    # Register the operation in PostgreSQL for client discovery.
    await context.stream_repo.register_operation(operation_id, stream.id, "chat")

    # Commit before launching the background producer — it creates its own
    # session and must be able to read the Stream/StreamProjection/Operation.
    await context.stream_repo.session.commit()

    _selected_nodes, model_message = parse_selected_nodes(message)

    if "v" not in _resolve_pipeline_holder:
        msg = (
            "Chat orchestrator not configured. "
            "Call services.chat.orchestrator.configure() at startup."
        )
        raise InternalError(detail=msg)

    turn = TurnIdentity(
        stream_id_str=stream_id_str,
        site_id=site_id,
        user_id=context.user_id,
        model_message=model_message,
    )

    stream_id_ctx.set(stream_id_str)
    operation_id_ctx.set(operation_id)

    # Launch the background producer as an asyncio task.
    task = create_detached_task(
        chat_producer(
            operation_id=operation_id,
            turn=turn,
            config=cfg,
            resolve_pipeline_fn=_resolve_pipeline_holder["v"],
        ),
        name=f"chat-producer:{operation_id}",
    )
    _active_tasks[operation_id] = task
    task.add_done_callback(lambda _: _active_tasks.pop(operation_id, None))

    return operation_id, stream_id_str, entry_id


async def start_plan_action_stream(
    *,
    site_id: str,
    strategy_id: UUID,
    context: ChatContext,
    config: ChatTurnConfig,
) -> tuple[str, str]:
    """Start a non-chat plan-action operation for an existing strategy."""
    await context.user_repo.get_or_create(context.user_id)

    stream = await context.stream_repo.get_by_id(strategy_id)
    if stream is None:
        raise InternalError(detail="Strategy stream not found for plan action.")

    operation_id = f"op_{uuid4().hex[:12]}"
    await context.stream_repo.register_operation(operation_id, stream.id, "plan_action")
    await context.stream_repo.session.commit()

    if "v" not in _resolve_pipeline_holder:
        msg = (
            "Chat orchestrator not configured. "
            "Call services.chat.orchestrator.configure() at startup."
        )
        raise InternalError(detail=msg)

    turn = TurnIdentity(
        stream_id_str=str(stream.id),
        site_id=site_id,
        user_id=context.user_id,
        model_message="",
    )

    stream_id_ctx.set(str(stream.id))
    operation_id_ctx.set(operation_id)

    task = create_detached_task(
        chat_producer(
            operation_id=operation_id,
            turn=turn,
            config=config,
            resolve_pipeline_fn=_resolve_pipeline_holder["v"],
        ),
        name=f"plan-action-producer:{operation_id}",
    )
    _active_tasks[operation_id] = task
    task.add_done_callback(lambda _: _active_tasks.pop(operation_id, None))

    return operation_id, str(stream.id)


async def cancel_chat_operation(operation_id: str) -> bool:
    """Cancel a running chat operation.

    Returns True if the operation was found and cancelled, False otherwise.

    After calling ``task.cancel()`` we await the task so that its
    CancelledError handler (handle_cancellation) actually runs.
    Without this, a cancel that arrives before the producer's first
    ``await`` would skip the handler entirely — no ``message_end``
    event, no status update, subscriber hangs forever.
    """
    task = _active_tasks.get(operation_id)
    if task is None:
        return False
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return True
