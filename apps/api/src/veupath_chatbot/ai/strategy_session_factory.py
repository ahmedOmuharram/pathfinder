"""Helpers for hydrating in-memory strategy session context for agents."""

from __future__ import annotations

from uuid import UUID

from veupath_chatbot.domain.strategy.ast import from_dict
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.strategy_session import (
    StrategyGraph,
    StrategySession,
    hydrate_graph_from_steps_data,
)

logger = get_logger(__name__)


def build_strategy_session(
    *,
    site_id: str,
    strategy_graph: dict | None,
) -> StrategySession:
    """Build a StrategySession from a persisted strategy graph payload.

    This mirrors UI persistence semantics:
    - Prefer canonical `plan` if present/parseable.
    - Fall back to snapshot-derived `steps` + `rootStepId` hydration when plan is missing/invalid.
    """

    session = StrategySession(site_id)

    if strategy_graph:
        graph_id = str(strategy_graph.get("id") or strategy_graph.get("graphId"))
        name = strategy_graph.get("name") or "Draft Strategy"
        plan = strategy_graph.get("plan")

        graph = StrategyGraph(graph_id, name, site_id)
        if plan:
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

        # If plan wasn't available/valid, fall back to persisted steps/rootStepId hydration.
        if not graph.steps:
            steps_data = strategy_graph.get("steps") or []
            root_step_id = strategy_graph.get("rootStepId") or strategy_graph.get(
                "root_step_id"
            )
            record_type = strategy_graph.get("recordType") or strategy_graph.get(
                "record_type"
            )
            try:
                hydrate_graph_from_steps_data(
                    graph,
                    steps_data if isinstance(steps_data, list) else [],
                    root_step_id=str(root_step_id) if root_step_id else None,
                    record_type=str(record_type) if record_type else None,
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

