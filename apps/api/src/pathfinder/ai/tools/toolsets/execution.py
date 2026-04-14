"""Execution-phase toolset — 12 tools for building and editing strategies."""

from pydantic_ai.tools import Tool
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.conversation import (
    clear_strategy,
    rename_strategy,
)
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


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the execution-phase toolset.

    Destructive graph-mutations (``delete_step`` and ``clear_strategy``)
    carry ``requires_approval=True`` so the v6 adapter emits a
    ``ToolApprovalRequestChunk`` instead of executing immediately. The
    client then prompts the user for approval before the destructive
    operation proceeds. See design Decision 8 + chat-overhaul
    section "Tool approvals".
    """
    return FunctionToolset(
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
            think,
        ],
    )
