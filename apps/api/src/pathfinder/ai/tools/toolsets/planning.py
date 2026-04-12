"""Planning-phase toolset — 8 tools for creating and managing execution plans."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone.artifact import set_conversation_title
from pathfinder.ai.tools.standalone.gene import resolve_gene_ids_to_records
from pathfinder.ai.tools.standalone.phase_decision import finish_planning
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
    """Build the planning-phase toolset."""
    return FunctionToolset(
        tools=[
            create_plan,
            get_plan,
            update_plan,
            submit_plan,
            present_decision,
            finish_planning,
            resolve_gene_ids_to_records,
            set_conversation_title,
            get_strategy,
            think,
        ],
    )
