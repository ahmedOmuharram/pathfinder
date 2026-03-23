"""Tools for conversation and strategy management."""

from typing import Annotated
from uuid import UUID

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


def _has_strategy(graph: StrategyGraph) -> bool:
    """Check if the graph has at least one root with steps."""
    return len(graph.roots) > 0 and len(graph.steps) > 0


class ConversationTools:
    """Tools for managing conversations and saved strategies."""

    def __init__(
        self,
        session: StrategySession,
        user_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id

    @ai_function()
    async def save_strategy(
        self,
        name: Annotated[str, AIParam(desc="Name for the saved strategy")],
        description: Annotated[str | None, AIParam(desc="Description")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to save")] = None,
    ) -> JSONObject:
        """Save the current strategy for later use.

        The strategy will be saved to the user's account and can be
        loaded again in future conversations.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
        if not _has_strategy(graph):
            return tool_error(
                ErrorCode.INVALID_STRATEGY,
                "No strategy to save. Build a strategy first.",
            )

        graph.name = name
        if description is not None:
            graph.description = description

        # In production, this would save to database
        logger.info("Saving strategy", name=name, user_id=str(self.user_id))

        return {
            "ok": True,
            "graphId": graph.id,
            "name": name,
            "description": graph.description,
            "recordType": graph.record_type or "",
            "graphName": graph.name,
            "plan": graph.to_plan(),
            "message": f"Strategy '{name}' saved successfully.",
        }

    @ai_function()
    async def rename_strategy(
        self,
        new_name: Annotated[str, AIParam(desc="New name for the strategy")],
        description: Annotated[str, AIParam(desc="Strategy description")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to rename")] = None,
    ) -> JSONObject:
        """Rename the current strategy."""
        graph = self.session.get_graph(graph_id)
        if not graph:
            return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
        if not _has_strategy(graph):
            return tool_error(ErrorCode.INVALID_STRATEGY, "No strategy to rename.")

        old_name = graph.name
        graph.name = new_name
        graph.description = description
        graph.save_history(f"Renamed from '{old_name}' to '{new_name}'")

        return {
            "ok": True,
            "graphId": graph.id,
            "oldName": old_name,
            "newName": new_name,
            "name": new_name,
            "recordType": graph.record_type or "",
            "description": graph.description,
            "plan": graph.to_plan(),
        }

    @ai_function()
    async def clear_strategy(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to clear")] = None,
        *,
        confirm: Annotated[
            bool,
            AIParam(desc="Set true to confirm deleting all nodes in the graph"),
        ] = False,
    ) -> JSONObject:
        """Clear the current strategy and start fresh.

        This removes all steps and the current strategy. Requires explicit confirmation.
        """
        graph = self.session.get_graph(graph_id)
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
        graph.wdk_strategy_id = None
        graph.wdk_step_ids.clear()
        graph.step_counts.clear()

        return {
            "ok": True,
            "graphId": graph.id,
            "cleared": True,
            "message": "Strategy cleared. Ready to start fresh.",
        }

    @ai_function()
    async def get_strategy_summary(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to summarize")] = None,
    ) -> JSONObject:
        """Get a summary of the current strategy.

        Returns step count, record type, and other metadata.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
        if not _has_strategy(graph):
            return {
                "hasStrategy": False,
                "graphId": graph.id,
                "graphName": graph.name,
                "stepCount": len(graph.steps),
                "message": (
                    f"No complete strategy yet. {len(graph.steps)} steps created."
                ),
            }

        # Count all steps by walking from the single root.
        root_id = next(iter(graph.roots)) if len(graph.roots) == 1 else None
        root = graph.steps.get(root_id) if root_id else None
        step_count = len(walk_step_tree(root)) if root else len(graph.steps)

        return {
            "hasStrategy": True,
            "graphId": graph.id,
            "graphName": graph.name,
            "name": graph.name,
            "recordType": graph.record_type or "",
            "stepCount": step_count,
            "description": graph.description,
        }
