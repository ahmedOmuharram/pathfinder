"""Scoping-phase toolset for framing the user's biological problem."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone.problem_framing import set_problem_frame
from pathfinder.ai.tools.standalone.research import literature_search, web_search
from pathfinder.ai.tools.standalone.think import think


def build_toolset() -> FunctionToolset[AgentDeps]:
    return FunctionToolset(
        tools=[
            set_problem_frame,
            web_search,
            literature_search,
            think,
        ],
    )
