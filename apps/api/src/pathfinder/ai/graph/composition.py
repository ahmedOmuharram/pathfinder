"""Where PathFinder is plugged into the turn graph.

The builder takes the product's hooks; this module is the one place that names
which hooks those are, so every process that runs a turn gets the same graph.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.lead_agent import build_lead_agent
from pathfinder.ai.lead.pre_turn import refresh_live_strategy_state

__all__ = ["build_pathfinder_graph"]


def build_pathfinder_graph(
    checkpointer: BaseCheckpointSaver[Any],
) -> CompiledStateGraph[PipelineState, Context, PipelineState, PipelineState]:
    return build_graph(
        checkpointer=checkpointer,
        pre_turn=refresh_live_strategy_state,
        build_agent=build_lead_agent,
    )
