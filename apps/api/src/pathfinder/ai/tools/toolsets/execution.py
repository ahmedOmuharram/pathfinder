"""Execution-phase toolset — tools for building and editing strategies."""

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import RunContext, Tool, ToolDefinition
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.prepared import PreparedToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.conversation import (
    clear_strategy,
    rename_strategy,
)
from pathfinder.ai.tools.standalone.escape_hatch import (
    request_search_inspection,
)
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
from pathfinder.ai.tools.standalone.strategy_attach import (
    add_step_analysis,
    add_step_filter,
    add_step_report,
)
from pathfinder.ai.tools.standalone.strategy_build import (
    combine_steps,
    create_leaf_step,
    transform_step,
)
from pathfinder.ai.tools.standalone.strategy_edit import (
    delete_step,
    undo_last_change,
    update_step,
)
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think
from pathfinder.ai.tools.toolsets._dynamic import (
    DynamicEnumToolset,
    EnumOverrides,
    live_step_ids,
)

_MAX_CONSECUTIVE_GET_STRATEGY = 2


def _get_strategy_repeated_without_mutation(
    ctx: RunContext[AgentDeps],
) -> bool:
    """True when the last calls in history are ``get_strategy`` repeated
    ≥ N times with no other tool between them. Any non-``get_strategy``
    call breaks the streak.
    """
    consecutive = 0
    for msg in reversed(ctx.messages):
        if not isinstance(msg, ModelResponse):
            continue
        for part in reversed(msg.parts):
            if not isinstance(part, ToolCallPart):
                continue
            if part.tool_name == "get_strategy":
                consecutive += 1
                if consecutive >= _MAX_CONSECUTIVE_GET_STRATEGY:
                    return True
            else:
                return False
    return False


async def _prepare(
    ctx: RunContext[AgentDeps], tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    if _get_strategy_repeated_without_mutation(ctx):
        return [td for td in tool_defs if td.name != "get_strategy"]
    return tool_defs


def _execution_enum_overrides(
    ctx: RunContext[AgentDeps],
) -> EnumOverrides:
    """Constrain step-id and search-name args to live-graph reality.

    * Every ``step_id`` arg → ``Literal[live_step_ids]``. The model
      literally cannot reference a step that doesn't exist in the
      strategy right now.
    * ``search_name`` args on step-creating tools → ``Literal``
      restricted to searches the discovery phase committed to.
      Combined with the F1/F2 work, the model can only build steps
      from searches it actually inspected and selected.
    """
    overrides: EnumOverrides = {}
    step_ids = live_step_ids(ctx.deps)
    if step_ids:
        for tool, arg in (
            ("combine_steps", "step_a_id"),
            ("combine_steps", "step_b_id"),
            ("transform_step", "input_step_id"),
            ("update_step", "step_id"),
            ("delete_step", "step_id"),
            ("add_step_filter", "step_id"),
            ("add_step_analysis", "step_id"),
            ("add_step_report", "step_id"),
        ):
            overrides[(tool, arg)] = step_ids
    selected = sorted(ctx.deps.agent_state.selected_search_names())
    if selected:
        overrides[("create_leaf_step", "search_name")] = selected
        overrides[("update_step", "search_name")] = selected
    return overrides


def build_toolset() -> AbstractToolset[AgentDeps]:
    base = FunctionToolset[AgentDeps](
        tools=[
            create_leaf_step,
            combine_steps,
            transform_step,
            update_step,
            Tool(delete_step, requires_approval=True),
            undo_last_change,
            add_step_filter,
            add_step_analysis,
            add_step_report,
            rename_strategy,
            Tool(clear_strategy, requires_approval=True),
            get_strategy,
            request_search_inspection,
            think,
            search_memory,
            remember,
        ],
    )
    return DynamicEnumToolset(
        wrapped=PreparedToolset(wrapped=base, prepare_func=_prepare),
        build_overrides=_execution_enum_overrides,
    )
