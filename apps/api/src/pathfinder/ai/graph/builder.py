from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.lead_node import lead_node
from pathfinder.ai.graph.nodes import finalize_turn_node
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState


def build_graph(
    *, checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[PipelineState, Context, PipelineState, PipelineState]:
    graph: StateGraph[PipelineState, Context, PipelineState, PipelineState] = (
        StateGraph(PipelineState, context_schema=Context)
    )
    graph.add_node("lead", lead_node)
    graph.add_node("finalize_turn", finalize_turn_node)
    graph.add_edge(START, "lead")
    return graph.compile(checkpointer=checkpointer)
