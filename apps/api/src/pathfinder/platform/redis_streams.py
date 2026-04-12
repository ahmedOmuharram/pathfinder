"""Shared Redis Stream append helper with observability instrumentation."""

import json
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from pathfinder.platform.metrics import (
    redis_stream_emit_attempts,
    redis_stream_emit_duration_s,
    redis_stream_events_emitted,
)
from pathfinder.platform.types import JSONObject


@dataclass(frozen=True)
class StreamAppendRequest:
    """Structured request for one Redis Stream append."""

    stream_key: str
    operation_id: str | None
    event_type: str
    event_data: JSONObject
    maxlen: int
    approximate: bool
    projected: bool = False
    committed: bool = False


def _stream_kind(stream_key: str) -> str:
    if stream_key.startswith("stream:"):
        return "conversation"
    if stream_key.startswith("op:"):
        return "operation"
    return "custom"


def _stream_metric_attrs(
    *,
    stream_key: str,
    event_type: str,
    projected: bool,
    committed: bool,
) -> dict[str, str]:
    return {
        "stream_kind": _stream_kind(stream_key),
        "event_type": event_type,
        "projected": str(projected).lower(),
        "committed": str(committed).lower(),
    }


async def append_stream_event(
    redis: Redis,
    request: StreamAppendRequest,
) -> str:
    """Append an event to a Redis Stream and record SigNoz-friendly metrics."""
    start = time.monotonic()
    metric_attrs = _stream_metric_attrs(
        stream_key=request.stream_key,
        event_type=request.event_type,
        projected=request.projected,
        committed=request.committed,
    )
    try:
        entry_id: str = await redis.xadd(
            request.stream_key,
            {
                "op": request.operation_id or "",
                "type": request.event_type,
                "data": json.dumps(request.event_data, default=str),
            },
            maxlen=request.maxlen,
            approximate=request.approximate,
        )
    except Exception:
        error_attrs = {**metric_attrs, "outcome": "error"}
        redis_stream_emit_attempts.add(1, error_attrs)
        redis_stream_emit_duration_s.record(time.monotonic() - start, error_attrs)
        raise

    success_attrs = {**metric_attrs, "outcome": "ok"}
    redis_stream_emit_attempts.add(1, success_attrs)
    redis_stream_emit_duration_s.record(time.monotonic() - start, success_attrs)
    redis_stream_events_emitted.add(1, metric_attrs)
    return entry_id
