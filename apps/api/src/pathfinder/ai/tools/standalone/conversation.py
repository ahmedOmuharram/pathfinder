"""Standalone conversation tools for pydantic-ai agents.

Provides:
- ``rename_strategy`` -- rename the current strategy
- ``clear_strategy`` -- clear the current strategy and start fresh
"""

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._conversation_models import (
    ClearStrategyResult,
    RenameStrategyResult,
    _has_strategy,
)
from pathfinder.platform.errors import ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.services.strategies.sync_state import WDKSyncState


async def rename_strategy(
    ctx: RunContext[AgentDeps],
    new_name: str,
    description: str,
    graph_id: str | None = None,
) -> RenameStrategyResult | ToolErrorPayload:
    """Rename the current strategy.

    Args:
        new_name: New name for the strategy.
        description: Strategy description.
        graph_id: Graph ID to rename.
    """
    session = ctx.deps.strategy_session
    graph = session.get_graph(graph_id)
    if not graph:
        return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
    if not _has_strategy(graph, session):
        return tool_error(ErrorCode.INVALID_STRATEGY, "No strategy to rename.")

    old_name = graph.name
    graph.name = new_name
    graph.description = description
    graph.save_history(f"Renamed from '{old_name}' to '{new_name}'")

    return RenameStrategyResult(
        graph_id=graph.id,
        old_name=old_name,
        new_name=new_name,
        name=new_name,
        record_type=graph.record_type or "",
        description=graph.description,
        plan=graph.to_plan(sync_state=session.sync_state),
    )


async def clear_strategy(
    ctx: RunContext[AgentDeps],
    graph_id: str | None = None,
    confirm: bool = False,
) -> ClearStrategyResult | ToolErrorPayload:
    """Clear the current strategy and start fresh.

    This removes all steps and the current strategy. Requires explicit confirmation.

    Args:
        graph_id: Graph ID to clear.
        confirm: Set true to confirm deleting all nodes in the graph.
    """
    session = ctx.deps.strategy_session
    graph = session.get_graph(graph_id)
    if not graph:
        return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
    if not confirm:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Refusing to clear the strategy without confirmation. Use confirm=true.",
            graphId=graph.id,
            requiresConfirmation=True,
        )

    graph.steps.clear()
    graph.roots.clear()
    graph.history.clear()
    graph.last_step_id = None
    # Reset WDK sync state.
    session.sync_state = WDKSyncState()

    return ClearStrategyResult(
        graph_id=graph.id,
        message="Strategy cleared. Ready to start fresh.",
    )
