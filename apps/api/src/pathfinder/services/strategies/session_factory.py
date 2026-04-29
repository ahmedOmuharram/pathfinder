"""Helpers for hydrating in-memory strategy session context for agents."""

from shared_py.defaults import DEFAULT_STREAM_NAME

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.domain.strategy.strategy_ast import PersistedStrategyGraph
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.sync_state import WDKSyncState

logger = get_logger(__name__)


def _restore_wdk_state(
    persisted: PersistedStrategyGraph, graph: StrategyGraph
) -> WDKSyncState:
    """Restore WDK state from persisted strategy graph payload."""
    sync_state = WDKSyncState()

    if persisted.wdk_strategy_id is not None:
        sync_state.wdk_strategy_id = persisted.wdk_strategy_id

    if persisted.strategy_ast is None:
        return sync_state

    payload = persisted.strategy_ast
    if payload.wdk_step_ids:
        for sid, wdk_step_id in payload.wdk_step_ids.items():
            if sid in graph.steps:
                sync_state.wdk_step_ids[sid] = wdk_step_id

    if payload.step_counts:
        for sid, count in payload.step_counts.items():
            if sid in graph.steps:
                sync_state.step_counts[sid] = count

    return sync_state


def build_strategy_session(
    *,
    site_id: str,
    strategy_graph: PersistedStrategyGraph | None,
) -> StrategySession:
    if strategy_graph is None or not strategy_graph.id:
        msg = (
            "build_strategy_session requires a PersistedStrategyGraph "
            "with id=str(conversation.id)"
        )
        raise ValueError(msg)

    session = StrategySession(site_id)
    name = strategy_graph.name or DEFAULT_STREAM_NAME
    graph = StrategyGraph(strategy_graph.id, name, site_id)
    if strategy_graph.strategy_ast is not None:
        payload = strategy_graph.strategy_ast
        try:
            graph.record_type = payload.record_type
            graph.name = payload.name or name
            all_steps = walk_step_tree(payload.root)
            graph.steps = {step.id: step for step in all_steps}
            graph.recompute_roots()
            graph.last_step_id = payload.root.id
            graph.description = payload.description
            graph.save_history(f"Loaded graph: {payload.name or name}")
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                "Failed to load graph plan",
                error=str(e),
                graph_id=strategy_graph.id,
            )

    session.sync_state = _restore_wdk_state(strategy_graph, graph)
    session.add_graph(graph)
    return session
