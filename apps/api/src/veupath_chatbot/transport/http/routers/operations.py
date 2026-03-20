"""Operations endpoints: subscribe via Redis Streams, discover active operations."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from veupath_chatbot.persistence.models import Operation, Stream
from veupath_chatbot.platform.errors import ForbiddenError, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.orchestrator import cancel_chat_operation
from veupath_chatbot.transport.http.deps import CurrentUser, DBSession
from veupath_chatbot.transport.http.sse import SSE_HEADERS

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

_EXPERIMENT_OP_TYPES = frozenset({"experiment", "batch", "benchmark"})


async def _verify_operation_access(
    session: DBSession, op: Operation, user_id: CurrentUser
) -> None:
    """Verify the current user owns the stream for non-experiment operations."""
    if op.type in _EXPERIMENT_OP_TYPES:
        return
    stream_result = await session.execute(
        select(Stream.user_id).where(Stream.id == op.stream_id)
    )
    stream_owner = stream_result.scalar_one_or_none()
    if stream_owner != user_id:
        raise ForbiddenError


# Event types that signal end of an operation.
_END_EVENT_TYPES = frozenset(
    {
        "message_end",
        "experiment_end",
        "batch_complete",
        "batch_error",
        "benchmark_complete",
        "benchmark_error",
        "seed_complete",
    }
)


@router.get("/{operation_id}/subscribe")
async def subscribe(
    operation_id: str,
    session: DBSession,
    user_id: CurrentUser,
    last_event_id: str | None = Query(
        default=None,
        alias="lastEventId",
        description="Resume from this Redis entry ID (for reconnection).",
    ),
) -> StreamingResponse:
    """SSE stream backed by Redis Streams.

    Catchup: replays events from `lastEventId` (or from the beginning).
    Live: uses XREAD BLOCK for new events until a terminal event is seen.
    """
    # Look up operation → stream mapping.
    result = await session.execute(
        select(Operation).where(Operation.operation_id == operation_id)
    )
    op = result.scalar_one_or_none()
    if op is None:
        raise NotFoundError(title="Operation not found")

    await _verify_operation_access(session, op, user_id)
    is_experiment = op.type in _EXPERIMENT_OP_TYPES
    stream_key = f"op:{operation_id}" if is_experiment else f"stream:{op.stream_id}"

    async def _stream() -> AsyncGenerator[str]:
        redis = get_redis()
        # Start position: after last_event_id, or from the beginning.
        cursor = last_event_id or "0-0"

        while True:
            # XREAD with BLOCK — waits for new events, returns when available.
            # Timeout of 15s triggers a keepalive comment.
            entries = await redis.xread({stream_key: cursor}, count=1, block=15000)

            if not entries:
                # No events within timeout — send keepalive comment.
                yield ":keepalive\n\n"

                # Only check operation status on keepalive (no events).
                # Checking after every event risks premature exit: a fast
                # producer may mark the operation "completed" while unread
                # events still sit in the stream.
                try:
                    result = await session.execute(
                        select(Operation.status).where(
                            Operation.operation_id == operation_id
                        )
                    )
                    status = result.scalar_one_or_none()
                    if status and status != "active":
                        return
                except OSError, RuntimeError:
                    logger.warning(
                        "Failed to check operation status",
                        operation_id=operation_id,
                        exc_info=True,
                    )
                continue

            for _stream_name, events in entries:
                for entry_id_bytes, fields in events:
                    entry_id = (
                        entry_id_bytes.decode()
                        if isinstance(entry_id_bytes, bytes)
                        else str(entry_id_bytes)
                    )
                    cursor = entry_id

                    # Filter by operation_id for shared streams (chat).
                    # Experiment streams are dedicated — no filtering needed.
                    if not is_experiment:
                        event_op = fields.get(b"op", b"").decode()
                        if event_op and event_op != operation_id:
                            continue

                    event_type = fields.get(b"type", b"progress").decode()
                    try:
                        data = json.loads(fields.get(b"data", b"{}"))
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to parse event data",
                            operation_id=operation_id,
                            entry_id=entry_id,
                        )
                        data = {}

                    yield f"id: {entry_id}\nevent: {event_type}\ndata: {json.dumps(data)}\n\n"

                    if event_type in _END_EVENT_TYPES:
                        return

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/{operation_id}/cancel", status_code=202)
async def cancel(
    operation_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> JSONObject:
    """Cancel a running operation.

    For chat operations this cancels the background asyncio task running
    the LLM agent. The producer's CancelledError handler emits a
    ``message_end`` event so any connected subscribers close cleanly.
    """
    result = await session.execute(
        select(Operation).where(Operation.operation_id == operation_id)
    )
    op = result.scalar_one_or_none()
    if op is None:
        raise NotFoundError(title="Operation not found")

    await _verify_operation_access(session, op, user_id)

    if op.status != "active":
        return {"operationId": operation_id, "status": op.status, "cancelled": False}

    cancelled = await cancel_chat_operation(operation_id)
    return {"operationId": operation_id, "cancelled": cancelled}


@router.get("/active")
async def list_active(
    session: DBSession,
    user_id: CurrentUser,
    stream_id: str | None = Query(
        default=None,
        alias="streamId",
        description="Filter by stream/strategy ID.",
    ),
    op_type: str | None = Query(
        default=None,
        alias="type",
        description="Filter by operation type (chat, experiment).",
    ),
) -> list[JSONObject]:
    """List active operations, optionally filtered by stream and/or type."""
    stmt = (
        select(Operation)
        .join(Stream, Operation.stream_id == Stream.id)
        .where(Operation.status == "active", Stream.user_id == user_id)
    )
    if stream_id:
        stmt = stmt.where(Operation.stream_id == stream_id)
    if op_type:
        stmt = stmt.where(Operation.type == op_type)

    result = await session.execute(stmt)
    ops = result.scalars().all()

    return [
        {
            "operationId": op.operation_id,
            "streamId": str(op.stream_id),
            "type": op.type,
            "status": op.status,
            "createdAt": op.created_at.isoformat() if op.created_at else None,
        }
        for op in ops
    ]
