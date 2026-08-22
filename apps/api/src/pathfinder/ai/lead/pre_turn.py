"""PathFinder's pre-turn refresh: measure the recorded build against WDK.

The user can edit the strategy between turns, in the graph editor or on the
site. WDK owns it, so only WDK can say what it holds now.
"""

from __future__ import annotations

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.domain.strategy.staleness import detect_build_staleness
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.services.strategies.live_counts import read_wdk_step_counts

__all__ = ["refresh_live_strategy_state"]


async def refresh_live_strategy_state(
    state: PipelineState,
    context: Context,
) -> PipelineState:
    """Return the state the turn runs on, with staleness measured live."""
    working_state = state.model_copy(deep=True)
    sync_state = context.strategy_session.sync_state
    live_counts = (
        await read_wdk_step_counts(sync_state, get_strategy_api(context.site_id))
        if sync_state is not None
        else {}
    )
    working_state.domain.stale_build = detect_build_staleness(
        working_state.domain.last_build_outcome,
        live_counts,
    )
    return working_state
