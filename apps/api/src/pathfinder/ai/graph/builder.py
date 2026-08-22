from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.lead_node import make_lead_node
from pathfinder.ai.graph.nodes import finalize_turn_node
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.lead_agent import LeadAgent
from pathfinder.assistant_core.graph.pre_turn import PreTurnHook
from pathfinder.assistant_core.graph.turn_agent import TurnAgentFactory


def build_graph(
    *,
    checkpointer: BaseCheckpointSaver[Any],
    pre_turn: PreTurnHook[PipelineState, Context],
    build_agent: TurnAgentFactory[LeadAgent],
) -> CompiledStateGraph[PipelineState, Context, PipelineState, PipelineState]:
    graph: StateGraph[PipelineState, Context, PipelineState, PipelineState] = (
        StateGraph(PipelineState, context_schema=Context)
    )
    graph.add_node(
        "lead",
        make_lead_node(pre_turn=pre_turn, build_agent=build_agent),
    )
    graph.add_node("finalize_turn", finalize_turn_node)
    graph.add_edge(START, "lead")
    return graph.compile(checkpointer=checkpointer)
