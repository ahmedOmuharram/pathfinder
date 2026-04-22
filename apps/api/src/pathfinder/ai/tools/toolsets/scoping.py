"""Scoping-phase toolset for framing the user's biological problem."""

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.prepared import PreparedToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.problem_framing import set_problem_frame
from pathfinder.ai.tools.standalone.research import literature_search, web_search
from pathfinder.ai.tools.standalone.think import think


def _tool_was_called(ctx: RunContext[AgentDeps], *names: str) -> bool:
    wanted = set(names)
    for msg in ctx.messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if isinstance(part, ToolCallPart) and part.tool_name in wanted:
                return True
    return False


async def _prepare(
    ctx: RunContext[AgentDeps], tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    # ``problem_frame_set_this_run`` is reset on every ``build_node_deps``
    # call, so this only short-circuits AFTER ``set_problem_frame`` ran in
    # the CURRENT phase invocation — preserving the one-shot contract
    # without silently zeroing the toolset on re-entry.
    if ctx.deps.problem_frame_set_this_run:
        return []
    if not _tool_was_called(ctx, "think"):
        return [td for td in tool_defs if td.name == "think"]
    if not _tool_was_called(ctx, "web_search", "literature_search"):
        return [
            td for td in tool_defs
            if td.name in {"think", "web_search", "literature_search"}
        ]
    return tool_defs


def build_toolset() -> AbstractToolset[AgentDeps]:
    base = FunctionToolset[AgentDeps](
        tools=[
            set_problem_frame,
            web_search,
            literature_search,
            think,
        ],
    )
    return PreparedToolset(wrapped=base, prepare_func=_prepare)
