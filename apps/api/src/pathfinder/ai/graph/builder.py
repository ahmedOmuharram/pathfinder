from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.nodes import (
    discovery_node,
    execution_node,
    planning_node,
    scoping_node,
    supervisor_node,
    verification_node,
)
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState


def build_graph(
    *, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[PipelineState, Context, PipelineState, PipelineState]:
    graph: StateGraph[PipelineState, Context, PipelineState, PipelineState] = (
        StateGraph(PipelineState, context_schema=Context)
    )
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("scoping", scoping_node)
    graph.add_node("discovery", discovery_node)
    graph.add_node("planning", planning_node)
    graph.add_node("execution", execution_node)
    graph.add_node("verification", verification_node)

    graph.add_edge(START, "supervisor")

    return graph.compile(checkpointer=checkpointer)
