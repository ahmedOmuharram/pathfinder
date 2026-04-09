"""Per-turn undo: truncate Redis events and rebuild the projection."""

import json
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.plan_payload import (
    PersistedStrategyGraph,
    StrategyPlanPayload,
)
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.persistence.models import Stream, StreamProjection
from pathfinder.platform.errors import NotFoundError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.projection import _PROJECTED_EVENT_TYPES, _project_event
from pathfinder.platform.redis import get_redis
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state

logger = get_logger(__name__)


class UndoResult:
    """Result of an undo operation."""

    __slots__ = ("message_count", "strategy", "wdk_strategy_id")

    def __init__(
        self,
        message_count: int,
        strategy: JSONObject | None,
        wdk_strategy_id: int | None,
    ) -> None:
        self.message_count = message_count
        self.strategy = strategy
        self.wdk_strategy_id = wdk_strategy_id


async def undo_turn(
    *,
    stream_id: UUID,
    entry_id: str,
    user_id: UUID,
    session: AsyncSession,
) -> UndoResult:
    """Undo a chat turn and all subsequent turns.

    Truncates the Redis stream from ``entry_id`` onward, rebuilds the
    PostgreSQL projection by replaying surviving events, and syncs WDK.
    """
    stream_id_str = str(stream_id)
    redis = get_redis()

    stream, projection = await _validate_ownership(session, stream_id, user_id)
    old_wdk_strategy_id = projection.wdk_strategy_id
    site_id = projection.site_id or stream.site_id

    await _truncate_redis(redis, stream_id_str, entry_id)
    new_state = await _replay_projection(redis, stream_id_str, session)

    # Parse plan once at the boundary — reused for WDK sync and response.
    try:
        reverted_plan = StrategyPlanPayload.model_validate(new_state.get("plan")) if new_state.get("plan") else None
    except (ValueError, TypeError):
        reverted_plan = None

    new_wdk_strategy_id = await _sync_wdk(
        site_id=site_id,
        old_wdk_strategy_id=old_wdk_strategy_id,
        reverted_plan=reverted_plan,
        new_state=new_state,
        stream_id_str=stream_id_str,
    )

    # Persist the new WDK strategy ID.
    await session.execute(
        update(StreamProjection)
        .where(StreamProjection.stream_id == stream_id)
        .values(wdk_strategy_id=new_wdk_strategy_id, is_saved=False)
    )
    await session.commit()

    strategy_response: JSONObject | None = (
        reverted_plan.model_dump(by_alias=True, exclude_none=True) if reverted_plan else None
    )
    raw_count = new_state.get("message_count", 0)
    msg_count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
    return UndoResult(
        message_count=msg_count,
        strategy=strategy_response,
        wdk_strategy_id=new_wdk_strategy_id,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _validate_ownership(
    session: AsyncSession, stream_id: UUID, user_id: UUID
) -> tuple[Stream, StreamProjection]:
    """Load stream + projection and verify ownership."""
    stream = await session.get(Stream, stream_id)
    if stream is None or stream.user_id != user_id:
        raise NotFoundError(detail="Stream not found")
    projection = await session.get(StreamProjection, stream_id)
    if projection is None:
        raise NotFoundError(detail="Stream not found")
    return stream, projection


async def _truncate_redis(redis: Redis, stream_id_str: str, entry_id: str) -> None:
    """Delete all Redis entries from *entry_id* onward."""
    entries = await redis.xrange(f"stream:{stream_id_str}", min=entry_id, max="+")
    if not entries:
        raise NotFoundError(detail="Entry ID not found in stream")

    first_id = entries[0][0]
    if first_id != entry_id:
        raise NotFoundError(detail="Entry ID not found in stream")

    ids = [eid for eid, _ in entries]
    await redis.xdel(f"stream:{stream_id_str}", *ids)
    logger.info(
        "Undo: deleted Redis entries",
        stream_id=stream_id_str,
        from_entry=entry_id,
        deleted_count=len(ids),
    )


async def _sync_wdk(
    *,
    site_id: str,
    old_wdk_strategy_id: int | None,
    reverted_plan: StrategyPlanPayload | None,
    new_state: JSONObject,
    stream_id_str: str,
) -> int | None:
    """Delete old WDK strategy and push reverted state if non-empty."""
    new_wdk_strategy_id: int | None = None

    if old_wdk_strategy_id is not None and site_id:
        await _delete_wdk_strategy(site_id, old_wdk_strategy_id)

    if site_id and reverted_plan is not None:
        new_wdk_strategy_id = await _push_reverted_strategy(
            site_id, stream_id_str, new_state, reverted_plan
        )

    return new_wdk_strategy_id


async def _delete_wdk_strategy(site_id: str, wdk_strategy_id: int) -> None:
    """Best-effort delete of a WDK strategy."""
    try:
        api = get_strategy_api(site_id)
        await api.delete_strategy(wdk_strategy_id)
        logger.info("Undo: deleted WDK strategy", wdk_strategy_id=wdk_strategy_id)
    except (OSError, ValueError, RuntimeError):
        logger.warning(
            "Undo: failed to delete WDK strategy (continuing)",
            wdk_strategy_id=wdk_strategy_id,
            exc_info=True,
        )


async def _push_reverted_strategy(
    site_id: str,
    stream_id_str: str,
    new_state: JSONObject,
    reverted_plan: StrategyPlanPayload,
) -> int | None:
    """Push the reverted plan to WDK. Returns the new strategy ID or None."""
    try:
        name_raw = new_state.get("name", DEFAULT_STREAM_NAME)
        name = str(name_raw) if name_raw and str(name_raw).strip() else DEFAULT_STREAM_NAME
        graph_payload = PersistedStrategyGraph(
            id=stream_id_str,
            name=name,
            plan=reverted_plan,
        )
        strat_session = build_strategy_session(
            site_id=site_id, strategy_graph=graph_payload
        )
        graph = strat_session.get_graph(None)
        if graph and graph.steps:
            sync_state = ensure_sync_state(strat_session)
            sync_result = await sync_strategy_for_site(
                graph=graph, sync_state=sync_state, site_id=site_id, strategy_name=graph.name
            )
            logger.info(
                "Undo: pushed reverted strategy to WDK",
                new_wdk_strategy_id=sync_result.wdk_strategy_id,
            )
            return sync_result.wdk_strategy_id
    except (OSError, ValueError, RuntimeError):
        logger.warning(
            "Undo: failed to push reverted strategy (continuing)",
            exc_info=True,
        )
    return None


async def _replay_projection(
    redis: Redis,
    stream_id: str,
    session: AsyncSession,
) -> JSONObject:
    """Reset the projection and replay all surviving events."""
    # Reset projection to blank state.
    blank: dict[str, object] = {
        "name": DEFAULT_STREAM_NAME,
        "record_type": None,
        "wdk_strategy_id": None,
        "is_saved": False,
        "model_id": None,
        "message_count": 0,
        "step_count": 0,
        "plan": {},
        "steps": [],
        "root_step_id": None,
        "estimated_size": None,
        "last_event_id": None,
        "updated_at": datetime.now(UTC),
    }
    await session.execute(
        update(StreamProjection)
        .where(StreamProjection.stream_id == stream_id)
        .values(**blank)
    )
    await session.flush()

    # Replay surviving events.
    entries = await redis.xrange(f"stream:{stream_id}")
    message_count = 0

    for raw_entry_id, fields in entries:
        event_type = fields.get("type", "")
        if event_type not in _PROJECTED_EVENT_TYPES:
            continue

        try:
            data: JSONObject = json.loads(fields["data"])
        except (json.JSONDecodeError, KeyError):
            continue

        # For message events, use absolute counts instead of SQL increments.
        if event_type in ("user_message", "assistant_message"):
            message_count += 1
            await session.execute(
                update(StreamProjection)
                .where(StreamProjection.stream_id == stream_id)
                .values(
                    message_count=message_count,
                    last_event_id=raw_entry_id,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.flush()
        else:
            await _project_event(session, stream_id, event_type, data, raw_entry_id)

    await session.flush()

    # Read back the rebuilt projection.
    session.expire_all()
    projection = await session.get(StreamProjection, stream_id)
    if projection is None:
        return {"message_count": 0, "plan": {}}

    return {
        "message_count": projection.message_count,
        "plan": projection.plan,
        "name": projection.name,
        "record_type": projection.record_type,
        "wdk_strategy_id": projection.wdk_strategy_id,
        "root_step_id": projection.root_step_id,
        "step_count": projection.step_count,
    }
