from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.nodes import (
    discovery_node,
    execution_node,
    planning_node,
    scoping_node,
    verification_node,
)
from pathfinder.ai.graph.router import (
    route_after_discovery,
    route_after_execution,
    route_after_planning,
    route_after_scoping,
    route_after_verification,
)
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState


def build_graph(
    *, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[PipelineState, Context, PipelineState, PipelineState]:
    graph: StateGraph[PipelineState, Context, PipelineState, PipelineState] = (
        StateGraph(PipelineState, context_schema=Context)
    )
    graph.add_node("scoping", scoping_node)
    graph.add_node("discovery", discovery_node)
    graph.add_node("planning", planning_node)
    graph.add_node("execution", execution_node)
    graph.add_node("verification", verification_node)

    graph.add_edge(START, "scoping")
    graph.add_conditional_edges(
        "scoping",
        route_after_scoping,
        ["discovery", "planning", END],
    )
    graph.add_conditional_edges(
        "discovery",
        route_after_discovery,
        ["planning", "execution", END],
    )
    graph.add_conditional_edges(
        "planning",
        route_after_planning,
        ["execution", END],
    )
    graph.add_conditional_edges(
        "execution",
        route_after_execution,
        ["execution", "verification", END],
    )
    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        [END],
    )

    return graph.compile(checkpointer=checkpointer)
