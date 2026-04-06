"""Operations endpoints: subscribe via Redis Streams, discover active operations."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from veupath_chatbot.persistence.models import Operation, Stream
from veupath_chatbot.platform.errors import ForbiddenError, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.orchestrator import cancel_chat_operation
from veupath_chatbot.transport.http.deps import CurrentUser, DBSession

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


async def _is_op_still_active(
    session: DBSession, operation_id: str,
) -> bool:
    """Check if an operation is still active. Returns False if finished or on error."""
    try:
        result = await session.execute(
            select(Operation.status).where(
                Operation.operation_id == operation_id
            )
        )
        status = result.scalar_one_or_none()
    except OSError, RuntimeError:
        logger.warning(
            "Failed to check operation status",
            operation_id=operation_id,
            exc_info=True,
        )
        return True
    else:
        return not status or status == "active"


def _decode_entry_id(entry_id_bytes: bytes | str) -> str:
    """Decode a Redis entry ID to a string."""
    return entry_id_bytes.decode() if hasattr(entry_id_bytes, "decode") else str(entry_id_bytes)


def _build_sse_event(entry_id: str, fields: dict[bytes, bytes], operation_id: str) -> ServerSentEvent:
    """Build a ``ServerSentEvent`` from a Redis stream entry."""
    event_type = fields.get(b"type", b"progress").decode()
    try:
        data = json.loads(fields.get(b"data", b"{}"))
    except json.JSONDecodeError:
        logger.warning("Failed to parse event data", operation_id=operation_id, entry_id=entry_id)
        data = {}
    return ServerSentEvent(data=data, event=event_type, id=entry_id)


async def _stream_events(
    *,
    stream_key: str,
    operation_id: str,
    session: DBSession,
    is_experiment: bool,
    start_cursor: str,
) -> AsyncGenerator[ServerSentEvent]:
    """SSE generator that reads from a Redis stream until a terminal event."""
    redis = get_redis()
    cursor = start_cursor

    while True:
        entries = await redis.xread({stream_key: cursor}, count=1, block=15000)

        if not entries:
            yield ServerSentEvent(comment="keepalive")
            if not await _is_op_still_active(session, operation_id):
                return
            continue

        for _stream_name, events in entries:
            for entry_id_bytes, fields in events:
                entry_id = _decode_entry_id(entry_id_bytes)
                cursor = entry_id

                if not is_experiment:
                    event_op = fields.get(b"op", b"").decode()
                    if event_op and event_op != operation_id:
                        continue

                yield _build_sse_event(entry_id, fields, operation_id)

                event_type = fields.get(b"type", b"progress").decode()
                if event_type in _END_EVENT_TYPES:
                    return


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
) -> EventSourceResponse:
    """SSE stream backed by Redis Streams."""
    result = await session.execute(
        select(Operation).where(Operation.operation_id == operation_id)
    )
    op = result.scalar_one_or_none()
    if op is None:
        raise NotFoundError(title="Operation not found")

    await _verify_operation_access(session, op, user_id)
    is_experiment = op.type in _EXPERIMENT_OP_TYPES
    stream_key = f"op:{operation_id}" if is_experiment else f"stream:{op.stream_id}"

    return EventSourceResponse(
        _stream_events(
            stream_key=stream_key,
            operation_id=operation_id,
            session=session,
            is_experiment=is_experiment,
            start_cursor=last_event_id or "0-0",
        ),
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
