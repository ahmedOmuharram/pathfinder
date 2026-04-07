"""Execution-phase toolset — 12 tools for building and editing strategies."""

from pydantic_ai.toolsets.function import FunctionToolset

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone.conversation import (
    clear_strategy,
    rename_strategy,
)
from veupath_chatbot.ai.tools.standalone.strategy_attach import (
    add_step_analysis,
    add_step_filter,
    add_step_report,
)
from veupath_chatbot.ai.tools.standalone.strategy_build import (
    combine_steps,
    create_leaf_step,
    transform_step,
)
from veupath_chatbot.ai.tools.standalone.strategy_edit import (
    delete_step,
    undo_last_change,
    update_step,
)
from veupath_chatbot.ai.tools.standalone.strategy_graph import get_strategy


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the execution-phase toolset."""
    return FunctionToolset(
        tools=[
            create_leaf_step,
            combine_steps,
            transform_step,
            update_step,
            delete_step,
            undo_last_change,
            add_step_filter,
            add_step_analysis,
            add_step_report,
            rename_strategy,
            clear_strategy,
            get_strategy,
        ],
    )
