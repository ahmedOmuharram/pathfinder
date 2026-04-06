"""Planning-phase toolset — 8 tools for creating and managing execution plans."""

from pydantic_ai.toolsets.function import FunctionToolset

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone.artifact import set_conversation_title
from veupath_chatbot.ai.tools.standalone.gene import resolve_gene_ids_to_records
from veupath_chatbot.ai.tools.standalone.plan import (
    create_plan,
    get_plan,
    present_decision,
    submit_plan,
    update_plan,
)
from veupath_chatbot.ai.tools.standalone.strategy_graph import get_strategy


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the planning-phase toolset."""
    return FunctionToolset(
        tools=[
            create_plan,
            get_plan,
            update_plan,
            submit_plan,
            present_decision,
            resolve_gene_ids_to_records,
            set_conversation_title,
            get_strategy,
        ],
    )
