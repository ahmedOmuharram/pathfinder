"""PathFinder's pre-turn refresh: measure the recorded build against WDK, and
give a strategy that has no spec one derived from what it already is.

The user can edit the strategy between turns, in the graph editor or on the
site. WDK owns it, so only WDK can say what it holds now.
"""

from __future__ import annotations

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.domain.strategy.spec_hydration import spec_from_ast
from pathfinder.domain.strategy.staleness import detect_build_staleness
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.services.strategies.live_counts import read_wdk_step_counts

__all__ = ["refresh_live_strategy_state"]


async def refresh_live_strategy_state(
    state: PipelineState,
    context: Context,
) -> PipelineState:
    """Return the state the turn runs on, with staleness measured live and the
    spec reconstructed when the strategy has one and the checkpoint does not."""
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
    _hydrate_spec_from_the_strategy(working_state, context)
    _record_the_spec_the_turn_started_from(working_state)
    return working_state


def _record_the_spec_the_turn_started_from(state: PipelineState) -> None:
    """Keep the entry spec an edit's dispositions are checked against.

    An approval-resume continues the turn that already recorded one, so it
    keeps that record rather than the spec the suspended pass had reached.
    """
    if state.pending_approval is not None:
        return
    entry_spec = state.domain.operational_spec
    state.domain.spec_before_turn = (
        None if entry_spec is None else entry_spec.model_copy(deep=True)
    )


def _hydrate_spec_from_the_strategy(state: PipelineState, context: Context) -> None:
    """Describe the live strategy as a spec when no framed spec describes it.

    The graph editor, a saved-strategy import and a checkpoint flush all leave
    a real strategy behind with nothing that says what it asks.
    """
    spec = state.domain.operational_spec
    if spec is not None and spec.criteria:
        return
    graph = context.strategy_session.get_graph(None)
    if graph is None or not graph.steps:
        return
    ast = graph.to_strategy_ast(sync_state=context.strategy_session.sync_state)
    if ast is None:
        return
    state.domain.operational_spec = spec_from_ast(ast, goal=state.user_prompt)
