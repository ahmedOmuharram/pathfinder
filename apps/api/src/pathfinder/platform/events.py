"""Event sourcing core: emit events to a Redis Stream."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.platform.projection import _project_event
from pathfinder.platform.redis_streams import StreamAppendRequest, append_stream_event
from pathfinder.platform.types import JSONObject

# Event types where the PostgreSQL projection MUST survive crashes.
# After projecting one of these, we commit immediately so that Redis
# and PostgreSQL stay consistent even if the process dies mid-stream.
_COMMIT_AFTER = frozenset(
    {
        "strategy_link",
        "graph_snapshot",
        "graph_plan",
        "model_selected",
    }
)


async def emit(
    redis: Redis,
    stream_id: str,
    operation_id: str | None,
    event_type: str,
    event_data: JSONObject,
    *,
    session: AsyncSession | None = None,
) -> str:
    """Append an event to a Redis Stream and optionally project to PostgreSQL.

    Returns the Redis entry ID (e.g. '1709234567890-0').
    """
    entry_id = await append_stream_event(
        redis,
        StreamAppendRequest(
            stream_key=f"stream:{stream_id}",
            operation_id=operation_id,
            event_type=event_type,
            event_data=event_data,
            maxlen=50_000,
            approximate=True,
            projected=session is not None,
            committed=session is not None and event_type in _COMMIT_AFTER,
        ),
    )

    if session:
        await _project_event(session, stream_id, event_type, event_data, entry_id)
        if event_type in _COMMIT_AFTER:
            await session.commit()

    return entry_id
