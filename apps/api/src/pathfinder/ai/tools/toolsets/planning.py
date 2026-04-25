"""Planning-phase toolset for creating and managing execution plans."""

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import RunContext, Tool, ToolDefinition
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.prepared import PreparedToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.escape_hatch import (
    request_search_inspection,
)
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

_READ_TOOLS = frozenset({"get_plan", "get_strategy"})
_MAX_CONSECUTIVE_READ = 2


def _loop_hidden_reads(ctx: RunContext[AgentDeps]) -> frozenset[str]:
    """Tail-only streak detection: any non-read tool breaks it."""
    counts: dict[str, int] = {}
    for msg in reversed(ctx.messages):
        if not isinstance(msg, ModelResponse):
            continue
        for part in reversed(msg.parts):
            if not isinstance(part, ToolCallPart):
                continue
            if part.tool_name in _READ_TOOLS:
                counts[part.tool_name] = counts.get(part.tool_name, 0) + 1
                continue
            return frozenset({n for n, c in counts.items() if c >= _MAX_CONSECUTIVE_READ})
    return frozenset({n for n, c in counts.items() if c >= _MAX_CONSECUTIVE_READ})


async def _prepare(
    ctx: RunContext[AgentDeps], tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    hidden = _loop_hidden_reads(ctx)
    if not hidden:
        return tool_defs
    return [td for td in tool_defs if td.name not in hidden]


def build_toolset() -> AbstractToolset[AgentDeps]:
    base = FunctionToolset[AgentDeps](
        tools=[
            create_plan,
            get_plan,
            update_plan,
            Tool(submit_plan, requires_approval=True),
            present_decision,
            resolve_gene_ids_to_records,
            get_strategy,
            request_search_inspection,
            think,
            search_memory,
            remember,
        ],
    )
    return PreparedToolset(wrapped=base, prepare_func=_prepare)
