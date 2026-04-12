"""Operations endpoints: subscribe via Redis Streams, discover active operations."""

import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select

from pathfinder.persistence.models import Operation, Stream
from pathfinder.platform.errors import ForbiddenError, NotFoundError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.orchestrator import cancel_chat_operation
from pathfinder.transport.http.deps import CurrentUser, DBSession
from pathfinder.transport.http.sse_observability import (
    SseSubscriptionTelemetry,
    finish_sse_subscription,
    start_sse_subscription,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

_EXPERIMENT_OP_TYPES = frozenset({"experiment", "batch", "benchmark"})

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


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def _resolve_operation(
    operation_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> Operation:
    """Look up an operation by ID and verify the caller owns it.

    Raises 404 if the operation doesn't exist and 403 if the caller
    isn't the stream owner.  Used as a FastAPI dependency so that auth
    checks run *before* the handler (and any SSE generator) starts.
    """
    result = await session.execute(
        select(Operation).where(Operation.operation_id == operation_id)
    )
    op = result.scalar_one_or_none()
    if op is None:
        raise NotFoundError(title="Operation not found")

    if op.type not in _EXPERIMENT_OP_TYPES:
        stream_result = await session.execute(
            select(Stream.user_id).where(Stream.id == op.stream_id)
        )
        stream_owner = stream_result.scalar_one_or_none()
        if stream_owner != user_id:
            raise ForbiddenError

    return op


VerifiedOp = Annotated[Operation, Depends(_resolve_operation)]


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


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


def _build_sse_event(entry_id: str, fields: dict[str, str], operation_id: str) -> ServerSentEvent:
    """Build a ``ServerSentEvent`` from a Redis stream entry."""
    event_type = fields.get("type", "progress")
    try:
        data = json.loads(fields.get("data", "{}"))
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
    telemetry: SseSubscriptionTelemetry,
) -> AsyncGenerator[ServerSentEvent]:
    """SSE generator that reads from a Redis stream until a terminal event."""
    redis = get_redis()
    cursor = start_cursor

    while True:
        entries = await redis.xread({stream_key: cursor}, count=1, block=15000)

        if not entries:
            telemetry.record_keepalive()
            yield ServerSentEvent(comment="keepalive")
            if not await _is_op_still_active(session, operation_id):
                telemetry.mark_disconnect("operation_inactive")
                return
            continue

        for _stream_name, events in entries:
            for entry_id, fields in events:
                cursor = entry_id

                if not is_experiment:
                    event_op = fields.get("op", "")
                    if event_op and event_op != operation_id:
                        continue

                event_type = fields.get("type", "progress")
                telemetry.record_event(event_type)
                yield _build_sse_event(entry_id, fields, operation_id)
                if event_type in _END_EVENT_TYPES:
                    telemetry.mark_terminal_event(event_type)
                    return


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{operation_id}/subscribe", response_class=EventSourceResponse)
async def subscribe(
    operation_id: str,
    session: DBSession,
    op: VerifiedOp,
    last_event_id: str | None = Query(
        default=None,
        alias="lastEventId",
        description="Resume from this Redis entry ID (for reconnection).",
    ),
) -> AsyncIterable[ServerSentEvent]:
    """SSE stream backed by Redis Streams.

    Auth and operation lookup are handled by the ``VerifiedOp`` dependency,
    so this handler is a clean async generator that FastAPI encodes into
    SSE wire format automatically.
    """
    is_experiment = op.type in _EXPERIMENT_OP_TYPES
    stream_key = f"op:{operation_id}" if is_experiment else f"stream:{op.stream_id}"
    telemetry = SseSubscriptionTelemetry(
        operation_id=operation_id,
        operation_type=op.type,
        stream_key=stream_key,
        resumed=last_event_id is not None,
        last_event_id=last_event_id,
    )
    start_sse_subscription(telemetry)

    try:
        async for event in _stream_events(
            stream_key=stream_key,
            operation_id=operation_id,
            session=session,
            is_experiment=is_experiment,
            start_cursor=last_event_id or "0-0",
            telemetry=telemetry,
        ):
            yield event
    except asyncio.CancelledError:
        telemetry.mark_disconnect("client_cancelled")
        raise
    except Exception:
        telemetry.mark_disconnect("stream_error")
        raise
    finally:
        finish_sse_subscription(telemetry)


@router.post("/{operation_id}/cancel", status_code=202)
async def cancel(
    operation_id: str,
    op: VerifiedOp,
) -> JSONObject:
    """Cancel a running operation.

    For chat operations this cancels the background asyncio task running
    the LLM agent. The producer's CancelledError handler emits a
    ``message_end`` event so any connected subscribers close cleanly.
    """
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
