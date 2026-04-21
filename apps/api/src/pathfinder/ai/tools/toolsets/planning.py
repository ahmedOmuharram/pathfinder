"""Planning-phase toolset for creating and managing execution plans."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.gene import resolve_gene_ids_to_records
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
from pathfinder.ai.tools.standalone.plan import (
    create_plan,
    get_plan,
    present_decision,
    submit_plan,
    update_plan,
)
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the planning-phase toolset.

    Phase exit is handled by ``output_type=PlanningDecision`` on the planning
    agent — no ``finish_*`` tool is exposed. ``submit_plan`` fires immediately
    and emits a ``data-plan-artifact`` chunk for the right-rail plan panel;
    the user then applies or discards the plan from the rail.
    """
    return FunctionToolset(
        tools=[
            create_plan,
            get_plan,
            update_plan,
            submit_plan,
            present_decision,
            resolve_gene_ids_to_records,
            get_strategy,
            think,
            search_memory,
            remember,
        ],
    )
