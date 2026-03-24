"""Helpers for hydrating in-memory strategy session context for agents."""

from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.domain.strategy.session import (
    StrategyGraph,
    StrategySession,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

from .schemas import StrategyPlanPayload

logger = get_logger(__name__)


def _restore_wdk_state(graph: StrategyGraph, strategy_graph: JSONObject) -> None:
    """Restore WDK build state (strategy ID, step IDs, counts) from plan metadata.

    Reads ``step_counts`` and ``wdk_step_ids`` from the plan payload stored in
    the persisted strategy graph payload.  If the plan is missing or
    unparseable, WDK state is simply not restored.
    """
    wdk_strategy_id = strategy_graph.get("wdkStrategyId")
    if isinstance(wdk_strategy_id, int):
        graph.wdk_strategy_id = wdk_strategy_id

    plan = strategy_graph.get("plan")
    if not isinstance(plan, dict):
        return
    try:
        payload = StrategyPlanPayload.model_validate(plan)
    except ValueError, TypeError, KeyError:
        return

    if payload.wdk_step_ids:
        for sid, wdk_step_id in payload.wdk_step_ids.items():
            if sid in graph.steps:
                graph.wdk_step_ids[sid] = wdk_step_id

    if payload.step_counts:
        for sid, count in payload.step_counts.items():
            if sid in graph.steps:
                graph.step_counts[sid] = count


def build_strategy_session(
    *,
    site_id: str,
    strategy_graph: JSONObject | None,
) -> StrategySession:
    """Build a StrategySession from a persisted strategy graph payload.

    Hydration uses the canonical ``plan`` field exclusively.  Legacy
    ``steps`` / ``rootStepId`` fallback has been removed.

    :param site_id: VEuPathDB site identifier.
    :param strategy_graph: JSONObject | None.
    """
    session = StrategySession(site_id)

    if strategy_graph:
        id_value = strategy_graph.get("id")
        graph_id_value = strategy_graph.get("graphId")
        graph_id_str: str | None = None
        if isinstance(id_value, str):
            graph_id_str = id_value
        elif isinstance(graph_id_value, str):
            graph_id_str = graph_id_value
        graph_id = graph_id_str or "unknown"

        name_value = strategy_graph.get("name")
        name = str(name_value) if isinstance(name_value, str) else DEFAULT_STREAM_NAME
        plan = strategy_graph.get("plan")

        graph = StrategyGraph(graph_id, name, site_id)
        if plan and isinstance(plan, dict):
            try:
                payload = StrategyPlanPayload.model_validate(plan)
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
                    graph_id=graph_id,
                )

        _restore_wdk_state(graph, strategy_graph)
        session.add_graph(graph)

    if not session.get_graph(None):
        session.create_graph(DEFAULT_STREAM_NAME)

    return session
