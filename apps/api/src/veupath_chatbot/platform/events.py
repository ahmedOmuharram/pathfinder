"""Event sourcing core: emit events to a Redis Stream.

The ``emit`` function is the single entry point for appending events.
It writes to Redis and optionally projects to PostgreSQL via
``platform.projection``.
"""

import json

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.platform.projection import _project_event
from veupath_chatbot.platform.types import JSONObject

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
    entry_id_bytes: bytes = await redis.xadd(
        f"stream:{stream_id}",
        {
            "op": (operation_id or "").encode(),
            "type": event_type.encode(),
            "data": json.dumps(event_data, default=str).encode(),
        },
    )
    entry_id = (
        entry_id_bytes.decode()
        if isinstance(entry_id_bytes, bytes)
        else str(entry_id_bytes)
    )

    if session:
        await _project_event(session, stream_id, event_type, event_data, entry_id)
        if event_type in _COMMIT_AFTER:
            await session.commit()

    return entry_id
