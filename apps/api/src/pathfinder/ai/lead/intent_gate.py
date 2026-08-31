"""Which of the Lead's tools this turn's intent may reach.

Building is a response to a request. A turn whose classification states
context, asks a question or stores a preference never sees the tools that
create or change a strategy.
"""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition

from pathfinder.ai.lead.intent import BUILDING_INTENTS
from pathfinder.ai.lead.sub_agent_tools import LeadDeps

# The tools that write: they frame, materialize, patch or check a strategy, or
# they edit the EDA analysis a step is exported from.
BUILDING_TOOLS: frozenset[str] = frozenset(
    {
        "frame_problem",
        "build_strategy",
        "edit_strategy",
        "recover_failed_steps",
        "verify_strategy",
        "open_eda_analysis",
        "set_eda_filters",
        "run_eda_compute",
        "create_eda_step",
    }
)


def turn_builds(deps: LeadDeps) -> bool:
    """Whether the intent governing this turn asks for a build."""
    intent = deps.intent
    return intent is not None and intent.classification in BUILDING_INTENTS


def hide_building_tools(
    ctx: RunContext[LeadDeps],
    tool_defs: list[ToolDefinition],
) -> list[ToolDefinition]:
    """Drop the building tools until the turn is classified as one that builds."""
    if turn_builds(ctx.deps):
        return tool_defs
    return [td for td in tool_defs if td.name not in BUILDING_TOOLS]


__all__ = ["BUILDING_TOOLS", "hide_building_tools", "turn_builds"]
