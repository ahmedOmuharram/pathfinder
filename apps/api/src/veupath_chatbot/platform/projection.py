"""PostgreSQL projection handlers for event sourcing.

Each handler updates columns on the StreamProjection row based on
the event type.  The ``_project_event`` coroutine is the ONLY code
path that writes to ``stream_projections``.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.domain.strategy.plan_ast import count_plan_nodes
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.platform.event_schemas import (
    GraphPlanEventData,
    GraphSnapshotEventData,
    ModelSelectedEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
)
from veupath_chatbot.platform.types import JSONObject

# Event types that update the PostgreSQL projection.  High-frequency
# streaming events (assistant_delta, tool_call_*, etc.) are skipped to
# avoid a DB round-trip per token.
_PROJECTED_EVENT_TYPES = frozenset(
    {
        "user_message",
        "assistant_message",
        "strategy_meta",
        "strategy_link",
        "graph_snapshot",
        "graph_plan",
        "model_selected",
        "graph_cleared",
    }
)


# ------------------------------------------------------------------
# Per-type handlers
# ------------------------------------------------------------------


def _project_strategy_meta(updates: dict[str, object], data: JSONObject) -> None:
    event = StrategyMetaEventData.model_validate(data)
    if event.name:
        updates["name"] = event.name
    if event.record_type:
        updates["record_type"] = event.record_type


def _project_strategy_link(updates: dict[str, object], data: JSONObject) -> None:
    event = StrategyLinkEventData.model_validate(data)
    if event.wdk_strategy_id is not None:
        updates["wdk_strategy_id"] = event.wdk_strategy_id
    if event.is_saved is not None:
        updates["is_saved"] = event.is_saved


def _project_graph_snapshot(updates: dict[str, object], data: JSONObject) -> None:
    event = GraphSnapshotEventData.model_validate(data)
    if not event.graph_snapshot:
        return
    snapshot = event.graph_snapshot
    if snapshot.steps:
        updates["step_count"] = len(snapshot.steps)
    if snapshot.root_step_id:
        updates["root_step_id"] = snapshot.root_step_id
    name = snapshot.name or snapshot.graph_name
    if name:
        updates["name"] = name
    if snapshot.record_type:
        updates["record_type"] = snapshot.record_type
    if snapshot.plan:
        updates["plan"] = snapshot.plan


def _project_graph_plan(updates: dict[str, object], data: JSONObject) -> None:
    event = GraphPlanEventData.model_validate(data)
    if event.plan:
        updates["plan"] = event.plan
        updates["step_count"] = count_plan_nodes(event.plan)
    if event.name:
        updates["name"] = event.name
    if event.record_type:
        updates["record_type"] = event.record_type


def _project_model_selected(updates: dict[str, object], data: JSONObject) -> None:
    event = ModelSelectedEventData.model_validate(data)
    updates["pipeline"] = event.pipeline.model_dump(by_alias=True)


def _project_graph_cleared(updates: dict[str, object]) -> None:
    updates["name"] = DEFAULT_STREAM_NAME
    updates["plan"] = {}
    updates["root_step_id"] = None
    updates["step_count"] = 0
    updates["wdk_strategy_id"] = None
    updates["is_saved"] = False


# Dispatch table for handlers that take (updates, data).
_PROJECTION_HANDLERS: dict[str, Callable[[dict[str, object], JSONObject], None]] = {
    "strategy_meta": _project_strategy_meta,
    "strategy_link": _project_strategy_link,
    "graph_snapshot": _project_graph_snapshot,
    "graph_plan": _project_graph_plan,
    "model_selected": _project_model_selected,
}


# ------------------------------------------------------------------
# Core projection entry point
# ------------------------------------------------------------------


async def _project_event(
    session: AsyncSession,
    stream_id: str,
    event_type: str,
    event_data: JSONObject,
    entry_id: str,
) -> None:
    """Update the PostgreSQL projection based on an event.

    This is the ONLY code path that writes to stream_projections.
    """
    if event_type not in _PROJECTED_EVENT_TYPES:
        return

    updates: dict[str, object] = {
        "last_event_id": entry_id,
        "updated_at": datetime.now(UTC),
    }

    if event_type in ("user_message", "assistant_message"):
        updates["message_count"] = StreamProjection.__table__.c.message_count + 1
    elif event_type == "graph_cleared":
        _project_graph_cleared(updates)
    else:
        handler = _PROJECTION_HANDLERS.get(event_type)
        if handler:
            handler(updates, event_data)

    # Pre-clear conflicting wdk_strategy_id before the main update.
    # WDK can reuse strategy IDs (same user, same search), so when
    # a new stream claims a WDK ID, the old owner must release it.
    if event_type == "strategy_link" and "wdk_strategy_id" in updates:
        wdk_id = updates["wdk_strategy_id"]
        clear_stmt = (
            update(StreamProjection)
            .where(StreamProjection.wdk_strategy_id == wdk_id)
            .where(StreamProjection.stream_id != stream_id)
            .values(wdk_strategy_id=None, is_saved=False)
        )
        await session.execute(clear_stmt)

    stmt = (
        update(StreamProjection)
        .where(StreamProjection.stream_id == stream_id)
        .values(**updates)
    )
    try:
        await session.execute(stmt)
        await session.flush()
    except Exception as exc:
        # Handle wdk_strategy_id unique constraint race: two concurrent workers
        # auto-build the same search -> both try to claim the same wdk_strategy_id.
        # The first commit wins; the second gets IntegrityError. Clear the old
        # owner and retry.
        if "ix_proj_wdk" in str(exc) and "wdk_strategy_id" in updates:
            await session.rollback()
            wdk_id = cast("int", updates["wdk_strategy_id"])
            clear_stmt = (
                update(StreamProjection)
                .where(StreamProjection.wdk_strategy_id == wdk_id)
                .where(StreamProjection.stream_id != stream_id)
                .values(wdk_strategy_id=None, is_saved=False)
            )
            await session.execute(clear_stmt)
            await session.execute(stmt)
            await session.flush()
        else:
            raise
