"""Scoping-phase toolset for framing the user's biological problem."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone.phase_decision import finish_scoping
from pathfinder.ai.tools.standalone.problem_framing import set_problem_frame
from pathfinder.ai.tools.standalone.research import literature_search, web_search
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the scoping-phase toolset."""
    return FunctionToolset(
        tools=[
            set_problem_frame,
            finish_scoping,
            web_search,
            literature_search,
            get_strategy,
            think,
        ],
    )
