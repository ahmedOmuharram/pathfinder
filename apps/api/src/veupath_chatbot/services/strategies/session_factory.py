"""Helpers for hydrating in-memory strategy session context for agents."""

from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.domain.strategy.session import (
    StrategyGraph,
    StrategySession,
    hydrate_graph_from_steps_data,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


def _restore_wdk_state(graph: StrategyGraph, strategy_graph: JSONObject) -> None:
    """Restore WDK build state (strategy ID, step IDs, counts) from persisted data.

    This runs regardless of whether the graph was loaded from plan or
    from steps hydration, because the plan AST doesn't carry WDK step
    IDs -- only the persisted steps snapshot does.
    """
    wdk_strategy_id = strategy_graph.get("wdkStrategyId")
    if isinstance(wdk_strategy_id, int):
        graph.wdk_strategy_id = wdk_strategy_id

    steps_data_for_wdk = strategy_graph.get("steps")
    if not isinstance(steps_data_for_wdk, list):
        return
    for step in steps_data_for_wdk:
        if not isinstance(step, dict):
            continue
        sid = step.get("id")
        if sid is None:
            continue
        sid = str(sid)
        wdk_step_id = step.get("wdkStepId")
        if isinstance(wdk_step_id, int) and sid in graph.steps:
            graph.wdk_step_ids[sid] = wdk_step_id
        result_count = step.get("resultCount") or step.get("estimatedSize")
        if isinstance(result_count, int) and sid in graph.steps:
            graph.step_counts[sid] = result_count


def _hydrate_graph_fallback(
    graph: StrategyGraph, strategy_graph: JSONObject, name: str
) -> None:
    """Fall back to persisted steps/rootStepId hydration when plan is missing."""
    steps_data_value = strategy_graph.get("steps")
    steps_data = steps_data_value if isinstance(steps_data_value, list) else []
    root_step_id_value = strategy_graph.get("rootStepId")
    root_step_id_alt = strategy_graph.get("root_step_id")
    root_step_id: str | None = None
    if isinstance(root_step_id_value, str):
        root_step_id = root_step_id_value
    elif isinstance(root_step_id_alt, str):
        root_step_id = root_step_id_alt
    record_type_value = strategy_graph.get("recordType")
    record_type_alt = strategy_graph.get("record_type")
    record_type: str | None = None
    if isinstance(record_type_value, str):
        record_type = record_type_value
    elif isinstance(record_type_alt, str):
        record_type = record_type_alt
    try:
        hydrate_graph_from_steps_data(
            graph,
            steps_data,
            root_step_id=root_step_id,
            record_type=record_type,
        )
        if graph.steps:
            graph.save_history(f"Loaded graph from persisted steps: {name}")
    except Exception as e:
        logger.warning(
            "Failed to hydrate graph from persisted steps",
            error=str(e),
            graph_id=graph.id,
        )


def build_strategy_session(
    *,
    site_id: str,
    strategy_graph: JSONObject | None,
) -> StrategySession:
    """Build a StrategySession from a persisted strategy graph payload.

    This mirrors UI persistence semantics: prefer canonical ``plan`` if
    present/parseable, fall back to snapshot-derived ``steps`` + ``rootStepId``
    hydration when plan is missing/invalid.

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
                strategy = from_dict(plan)
                graph.current_strategy = strategy
                graph.name = strategy.name or name
                graph.steps = {step.id: step for step in strategy.get_all_steps()}
                graph.recompute_roots()
                graph.last_step_id = strategy.root.id
                graph.save_history(f"Loaded graph: {strategy.name or name}")
            except Exception as e:
                logger.warning(
                    "Failed to load graph plan",
                    error=str(e),
                    graph_id=graph_id,
                )

        if not graph.steps:
            _hydrate_graph_fallback(graph, strategy_graph, name)

        _restore_wdk_state(graph, strategy_graph)
        session.add_graph(graph)

    if not session.get_graph(None):
        session.create_graph(DEFAULT_STREAM_NAME)

    return session
