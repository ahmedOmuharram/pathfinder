"""Best-effort auto-push: sync a local strategy back to VEuPathDB WDK.

Called after strategy mutations (CRUD updates, chat-driven changes) when
the strategy has a ``wdk_strategy_id``.  Failures are logged but never
propagate — the local save is the source of truth.

IMPORTANT: this runs as a background ``asyncio.Task``, **not** inside the
request's DB session.  It creates its own session to avoid the
``asyncpg InterfaceError: another operation is in progress`` that occurs
when a fire-and-forget task shares a request-scoped connection.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise

logger = get_logger(__name__)

# Per-strategy lock to prevent concurrent auto-pushes from racing on
# the same DB row / WDK strategy.
_push_locks: dict[UUID, asyncio.Lock] = {}
_PUSH_LOCKS_MAX = 200


def _get_push_lock(strategy_id: UUID) -> asyncio.Lock:
    """Return (or create) an asyncio.Lock for the given strategy."""
    if strategy_id not in _push_locks:
        # Evict oldest entries to bound memory.
        if len(_push_locks) >= _PUSH_LOCKS_MAX:
            oldest = next(iter(_push_locks))
            del _push_locks[oldest]
        _push_locks[strategy_id] = asyncio.Lock()
    return _push_locks[strategy_id]


async def try_auto_push_to_wdk(
    strategy_id: UUID,
    # strategy_repo is accepted for API compat but NOT used — we create
    # our own session to avoid sharing the request-scoped connection.
    strategy_repo: StrategyRepository | None = None,
) -> None:
    """Push a strategy to WDK if it has a ``wdk_strategy_id``.

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
            repo = StrategyRepository(session)
            strategy = await repo.get_by_id(strategy_id)
            if not strategy or not strategy.wdk_strategy_id:
                return

            plan = strategy.plan if isinstance(strategy.plan, dict) else {}
            if not plan:
                return

            strategy_ast = validate_plan_or_raise(plan)
            api = get_strategy_api(strategy.site_id)

            result = await compile_strategy(strategy_ast, api, site_id=strategy.site_id)

            await api.update_strategy(
                strategy_id=strategy.wdk_strategy_id,
                step_tree=result.step_tree,
                name=strategy.name,
            )

            # Rewrite local IDs to WDK IDs in the persisted plan.
            compiled_map = {s.local_id: s.wdk_step_id for s in result.steps}
            for step in strategy_ast.get_all_steps():
                wdk_step_id = compiled_map.get(step.id)
                if wdk_step_id:
                    step.id = str(wdk_step_id)

            await repo.update(
                strategy_id=strategy_id,
                plan=strategy_ast.to_dict(),
                record_type=strategy_ast.record_type,
            )
            await session.commit()

            logger.info(
                "Auto-pushed strategy to WDK",
                strategy_id=str(strategy_id),
                wdk_strategy_id=strategy.wdk_strategy_id,
            )
        except WDKError as e:
            await session.rollback()
            if e.status == 404:
                # The WDK strategy no longer exists — clear the stale
                # reference so we stop retrying on every save.
                logger.warning(
                    "WDK strategy no longer exists, clearing wdk_strategy_id",
                    strategy_id=str(strategy_id),
                )
                try:
                    repo = StrategyRepository(session)
                    await repo.update(
                        strategy_id=strategy_id,
                        wdk_strategy_id=None,
                        wdk_strategy_id_set=True,
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.error(
                        "Failed to clear stale wdk_strategy_id",
                        strategy_id=str(strategy_id),
                    )
            else:
                logger.warning(
                    "Auto-push to WDK failed (best-effort)",
                    strategy_id=str(strategy_id),
                    error=str(e),
                )
        except Exception as e:
            await session.rollback()
            logger.warning(
                "Auto-push to WDK failed (best-effort)",
                strategy_id=str(strategy_id),
                error=str(e),
            )
