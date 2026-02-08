"""Helpers for hydrating in-memory strategy session context for agents."""

from __future__ import annotations

from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategy_session import (
    StrategyGraph,
    StrategySession,
    hydrate_graph_from_steps_data,
)

logger = get_logger(__name__)


def build_strategy_session(
    *,
    site_id: str,
    strategy_graph: JSONObject | None,
) -> StrategySession:
    """Build a StrategySession from a persisted strategy graph payload.

    This mirrors UI persistence semantics:
    - Prefer canonical `plan` if present/parseable.
    - Fall back to snapshot-derived `steps` + `rootStepId` hydration when
      plan is missing/invalid.
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
        name = str(name_value) if isinstance(name_value, str) else "Draft Strategy"
        plan = strategy_graph.get("plan")

        graph = StrategyGraph(graph_id, name, site_id)
        if plan and isinstance(plan, dict):
            try:
                strategy = from_dict(plan)
                graph.current_strategy = strategy
                graph.name = strategy.name or name
                graph.steps = {step.id: step for step in strategy.get_all_steps()}
                graph.last_step_id = strategy.root.id
                graph.save_history(f"Loaded graph: {strategy.name or name}")
            except Exception as e:
                logger.warning(
                    "Failed to load graph plan",
                    error=str(e),
                    graph_id=graph_id,
                )

        # If plan wasn't available/valid, fall back to persisted steps/
        # rootStepId hydration.
        if not graph.steps:
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
                    graph_id=graph_id,
                )

        session.add_graph(graph)

    if not session.get_graph(None):
        session.create_graph("Draft Strategy")

    return session
