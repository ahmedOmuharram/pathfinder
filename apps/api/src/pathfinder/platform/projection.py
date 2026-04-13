"""PostgreSQL projection handlers for event sourcing.

Each handler updates columns on the StreamProjection row based on
the event type.  The ``_project_event`` coroutine is the ONLY code
path that writes to ``stream_projections``.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from pydantic import ConfigDict, ValidationError
from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.conversation_state import ConversationState
from pathfinder.domain.strategy.plan_ast import count_plan_nodes, derive_plan_steps_json
from pathfinder.persistence.models import StreamProjection
from pathfinder.platform.event_schemas import (
    GraphPlanEventData,
    GraphSnapshotEventData,
    ModelSelectedEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
)
from pathfinder.platform.event_schemas_pipeline import (
    PhaseChangeEventData,
    PlanApprovedEventData,
    PlanPresentedEventData,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class _PlanIdPayload(CamelModel):
    """Minimal typed view of a plan dict for projection — only ``id`` matters."""

    model_config = ConfigDict(extra="ignore")
    id: str

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
        "phase_change",
        "plan_presented",
        "plan_approved",
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
        updates["steps"] = snapshot.steps
    if snapshot.root_step_id:
        updates["root_step_id"] = snapshot.root_step_id
    name = snapshot.name or snapshot.graph_name
    if name:
        updates["name"] = name
    if snapshot.record_type:
        updates["record_type"] = snapshot.record_type
    if snapshot.plan:
        updates["plan"] = snapshot.plan.model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )


def _project_graph_plan(updates: dict[str, object], data: JSONObject) -> None:
    event = GraphPlanEventData.model_validate(data)
    if event.plan:
        updates["plan"] = event.plan.model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )
        updates["step_count"] = count_plan_nodes(event.plan)
        updates["steps"] = derive_plan_steps_json(event.plan)
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
    updates["steps"] = []
    updates["wdk_strategy_id"] = None
    updates["is_saved"] = False
    updates["conversation_state"] = {}


def _extract_phase_change(
    existing: ConversationState, data: JSONObject,
) -> ConversationState | None:
    try:
        parsed = PhaseChangeEventData.model_validate(data)
    except ValidationError:
        return None
    return existing.with_phase_change(
        parsed.phase,
        parsed.status,
        emitted_at=parsed.emitted_at,
        phase_started_at=parsed.phase_started_at,
        phase_completed_at=parsed.phase_completed_at,
        duration_ms=parsed.duration_ms,
    )


def _extract_plan_presented(
    existing: ConversationState, data: JSONObject,
) -> ConversationState | None:
    """Parse ``plan_presented`` via typed models — no isinstance chains."""
    try:
        event = PlanPresentedEventData.model_validate(data)
    except ValidationError:
        return None
    try:
        plan = _PlanIdPayload.model_validate(event.plan)
    except ValidationError:
        return None
    return existing.with_plan_event("plan_presented", plan_id=plan.id)


def _extract_plan_approved(
    existing: ConversationState, data: JSONObject,
) -> ConversationState | None:
    """Parse ``plan_approved`` via typed model.

    ``CamelModel`` has ``populate_by_name=True``, so both ``planId`` and
    ``plan_id`` are accepted — no manual snake_case fallback needed.
    """
    try:
        event = PlanApprovedEventData.model_validate(data)
    except ValidationError:
        return None
    return existing.with_plan_event("plan_approved", plan_id=event.plan_id)


def _extract_model_selected(
    existing: ConversationState, data: JSONObject,
) -> ConversationState | None:
    try:
        parsed = ModelSelectedEventData.model_validate(data)
    except ValidationError:
        return None
    pipeline_dict: dict[str, dict[str, str]] = {
        phase_name: {
            "modelId": phase_cfg.model_id,
            "reasoningEffort": phase_cfg.reasoning_effort,
        }
        for phase_name, phase_cfg in (
            ("scoping", parsed.pipeline.scoping),
            ("discovery", parsed.pipeline.discovery),
            ("planning", parsed.pipeline.planning),
            ("execution", parsed.pipeline.execution),
            ("verification", parsed.pipeline.verification),
        )
    }
    return existing.with_pipeline(pipeline_dict)


_CONVERSATION_STATE_HANDLERS: dict[
    str, Callable[[ConversationState, JSONObject], ConversationState | None]
] = {
    "phase_change": _extract_phase_change,
    "plan_presented": _extract_plan_presented,
    "plan_approved": _extract_plan_approved,
    "model_selected": _extract_model_selected,
}


def _build_conversation_state_update(
    existing: ConversationState,
    event_type: str,
    event_data: JSONObject,
) -> ConversationState | None:
    """Compute the next ConversationState from an event.

    Returns ``None`` if the event does not affect conversation state.
    Pure function — no I/O.
    """
    if event_type == "message_end":
        return existing
    handler = _CONVERSATION_STATE_HANDLERS.get(event_type)
    if handler is None:
        return None
    return handler(existing, event_data)


# Dispatch table for handlers that take (updates, data).
_PROJECTION_HANDLERS: dict[str, Callable[[dict[str, object], JSONObject], None]] = {
    "strategy_meta": _project_strategy_meta,
    "strategy_link": _project_strategy_link,
    "graph_snapshot": _project_graph_snapshot,
    "graph_plan": _project_graph_plan,
    "model_selected": _project_model_selected,
}


# ------------------------------------------------------------------
# Conversation state read-modify-write
# ------------------------------------------------------------------

_CONVERSATION_STATE_EVENT_TYPES = frozenset(
    {"phase_change", "plan_presented", "plan_approved", "model_selected"}
)


async def _project_conversation_state(
    session: AsyncSession,
    stream_id: str,
    event_type: str,
    event_data: JSONObject,
    updates: dict[str, object],
) -> None:
    """Read-modify-write the conversation_state column.

    Safe: only ONE writer per stream_id exists (the producer task).
    """
    existing_row = await session.execute(
        select(StreamProjection.conversation_state).where(
            StreamProjection.stream_id == stream_id
        )
    )
    raw_state = existing_row.scalar_one_or_none() or {}
    existing_state = ConversationState.model_validate(raw_state)
    new_state = _build_conversation_state_update(
        existing_state, event_type, event_data
    )
    if new_state is not None:
        updates["conversation_state"] = new_state.model_dump(
            by_alias=True, mode="json"
        )


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

    if event_type in _CONVERSATION_STATE_EVENT_TYPES:
        await _project_conversation_state(
            session, stream_id, event_type, event_data, updates
        )

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
