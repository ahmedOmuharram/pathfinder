"""The PathFinder tool names the runtime's guards key on.

The guards are generic mechanisms: one blocks a repeated read-only call, the
other gives a search-specific hint on a 404. Which tools those are is
PathFinder's vocabulary, and it lives here.
"""

from __future__ import annotations

from assistant_core.capabilities.repetition_guard import ToolRepetitionGuard

__all__ = [
    "GRAPH_MODIFYING_TOOLS",
    "READ_ONLY_TOOLS",
    "SEARCH_LOOKUP_TOOLS",
    "build_tool_repetition_guard",
]

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "get_strategy",
        "get_plan",
        "get_step_preview",
        "get_step_results",
        "get_record_detail",
        "get_records",
        "get_attributes",
        "get_distribution",
        "search_catalog",
        "text_search",
    }
)

GRAPH_MODIFYING_TOOLS: frozenset[str] = frozenset(
    {
        "create_leaf_step",
        "create_combined_step",
        "create_transform_step",
        "update_step",
        "combine_steps",
        "apply_view_filter",
        "delete_view_filter",
        "update_search_config",
    }
)

# A 404 from one of these means the search name does not exist on the site,
# which needs different advice from a 404 anywhere else.
SEARCH_LOOKUP_TOOLS: frozenset[str] = frozenset(
    {
        "get_search_overview",
        "get_parameter_options",
    }
)


def build_tool_repetition_guard() -> ToolRepetitionGuard:
    """A repetition guard that watches PathFinder's read-only tools."""
    return ToolRepetitionGuard(
        read_only_tools=READ_ONLY_TOOLS,
        graph_modifying_tools=GRAPH_MODIFYING_TOOLS,
    )
