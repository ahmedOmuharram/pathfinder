"""Best-effort auto-push: sync a local strategy back to VEuPathDB WDK.

Called after strategy mutations (CRUD updates, chat-driven changes) when
the strategy has a ``wdk_strategy_id``.  Failures are logged but never
propagate — the local save is the source of truth.

IMPORTANT: this runs as a background ``asyncio.Task``, **not** inside the
request's DB session.  It creates its own session to avoid the
``asyncpg InterfaceError: another operation is in progress`` that occurs
when a fire-and-forget task shares a request-scoped connection.
"""

import asyncio
from uuid import UUID

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.persistence.repositories.stream import (
    ProjectionUpdate,
    StreamRepository,
)
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.errors import AppError, WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.sync import sync_strategy_for_site
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload

logger = get_logger(__name__)

_HTTP_NOT_FOUND = 404

# Per-strategy lock to prevent concurrent auto-pushes from racing on
# the same DB row / WDK strategy.
_push_locks: dict[UUID, asyncio.Lock] = {}
_PUSH_LOCKS_MAX = 200


def _get_push_lock(strategy_id: UUID) -> asyncio.Lock:
    """Get or create a per-strategy lock for serialising WDK push operations.

    :param strategy_id: Strategy UUID.
    :returns: Asyncio lock for the given strategy.
    """
    if strategy_id not in _push_locks:
        # Evict oldest *unlocked* entries to bound memory.
        if len(_push_locks) >= _PUSH_LOCKS_MAX:
            to_evict: UUID | None = None
            for candidate, lock in _push_locks.items():
                if not lock.locked():
                    to_evict = candidate
                    break
            if to_evict is not None:
                del _push_locks[to_evict]
        _push_locks[strategy_id] = asyncio.Lock()
    return _push_locks[strategy_id]


async def _clear_stale_wdk_id(
    session: object,
    strategy_id: UUID,
) -> None:
    """Best-effort: clear a stale wdk_strategy_id after a 404 from WDK."""
    logger.warning(
        "WDK strategy no longer exists, clearing wdk_strategy_id",
        strategy_id=str(strategy_id),
    )
    try:
        repo = StreamRepository(session)
        await repo.update_projection(
            strategy_id,
            ProjectionUpdate(
                wdk_strategy_id=None,
                wdk_strategy_id_set=True,
            ),
        )
        await session.commit()
    except AppError, RuntimeError:
        await session.rollback()
        logger.exception(
            "Failed to clear stale wdk_strategy_id",
            strategy_id=str(strategy_id),
        )


def _build_graph_from_plan(
    payload: StrategyPlanPayload,
    site_id: str,
    wdk_strategy_id: int | None,
) -> StrategyGraph:
    """Build a temporary StrategyGraph from a validated plan payload.

    Populates steps, roots, record_type, and wdk_step_ids so
    ``sync_strategy_for_site`` can build the WDK step tree.
    """
    graph = StrategyGraph("auto-push", payload.name or "auto-push", site_id)
    graph.record_type = payload.record_type
    graph.wdk_strategy_id = wdk_strategy_id

    all_steps = walk_step_tree(payload.root)
    graph.steps = {step.id: step for step in all_steps}
    graph.recompute_roots()
    graph.last_step_id = payload.root.id

    # Hydrate wdk_step_ids from the plan payload (WDK-imported strategies
    # store mappings, and strategies with numeric IDs self-map).
    if payload.wdk_step_ids:
        graph.wdk_step_ids = dict(payload.wdk_step_ids)
    else:
        # For WDK-imported strategies, step IDs ARE WDK step IDs.
        for step in all_steps:
            if step.id.isdigit():
                graph.wdk_step_ids[step.id] = int(step.id)

    return graph


async def _do_push(
    session: object,
    strategy_id: UUID,
) -> None:
    """Run the actual sync-and-push flow inside an existing DB session."""
    repo = StreamRepository(session)
    projection = await repo.get_projection(strategy_id)
    if not projection or not projection.wdk_strategy_id:
        return

    site_id = projection.site_id
    if not site_id:
        return

    plan = projection.plan if isinstance(projection.plan, dict) else {}
    if not plan:
        return

    payload = validate_plan_or_raise(plan)
    graph = _build_graph_from_plan(payload, site_id, projection.wdk_strategy_id)

    sync_result = await sync_strategy_for_site(
        graph=graph,
        site_id=site_id,
        strategy_name=projection.name,
    )

    # Serialize updated plan from graph state (now has WDK step IDs and counts).
    updated_plan = graph.to_plan()
    await repo.update_projection(
        strategy_id,
        ProjectionUpdate(
            plan=updated_plan,
            record_type=graph.record_type,
            step_count=sync_result.step_count,
        ),
    )
    await session.commit()

    logger.info(
        "Auto-pushed strategy to WDK",
        strategy_id=str(strategy_id),
        wdk_strategy_id=sync_result.wdk_strategy_id,
    )


async def try_auto_push_to_wdk(
    strategy_id: UUID,
) -> None:
    """Push a strategy to WDK if it has a ``wdk_strategy_id``.

    Reads from the CQRS projection (stream_projections table).

    This is a best-effort operation — any error is logged and swallowed.

    If the WDK strategy no longer exists (404), the stale
    ``wdk_strategy_id`` is cleared so future pushes don't keep failing.
    """
    lock = _get_push_lock(strategy_id)
    if lock.locked():
        # Another push for this strategy is already in flight — skip.
        logger.debug(
            "Auto-push skipped (already in progress)",
            strategy_id=str(strategy_id),
        )
        return

    # Use an independent DB session so we don't contend with the
    # request-scoped session that fired this background task.
    async with lock, async_session_factory() as session:
        try:
            await _do_push(session, strategy_id)
        except WDKError as e:
            await session.rollback()
            if e.status == _HTTP_NOT_FOUND:
                await _clear_stale_wdk_id(session, strategy_id)
            else:
                logger.warning(
                    "Auto-push to WDK failed (best-effort)",
                    strategy_id=str(strategy_id),
                    error=str(e),
                )
        except (AppError, RuntimeError) as e:
            await session.rollback()
            logger.warning(
                "Auto-push to WDK failed (best-effort)",
                strategy_id=str(strategy_id),
                error=str(e),
            )
