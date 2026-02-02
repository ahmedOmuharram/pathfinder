"""Tools for conversation and strategy management."""

from typing import Annotated, Any
from uuid import UUID

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.services.strategy_session import StrategySession

logger = get_logger(__name__)


class ConversationTools:
    """Tools for managing conversations and saved strategies."""

    def __init__(
        self,
        session: StrategySession,
        user_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id

    def _tool_error(self, code: ErrorCode | str, message: str, **details: Any) -> dict[str, Any]:
        return tool_error(code, message, **details)

    @ai_function()
    async def save_strategy(
        self,
        name: Annotated[str, AIParam(desc="Name for the saved strategy")],
        description: Annotated[str | None, AIParam(desc="Description")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to save")] = None,
    ) -> dict[str, Any]:
        """Save the current strategy for later use.

        The strategy will be saved to the user's account and can be
        loaded again in future conversations.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        if not graph.current_strategy:
            return self._tool_error(
                ErrorCode.INVALID_STRATEGY,
                "No strategy to save. Build a strategy first.",
            )

        strategy = graph.current_strategy
        strategy.name = name
        if description is not None:
            strategy.description = description
        graph.name = name

        # In production, this would save to database
        logger.info("Saving strategy", name=name, user_id=str(self.user_id))

        return {
            "ok": True,
            "graphId": graph.id,
            "name": name,
            "description": strategy.description,
            "recordType": strategy.record_type,
            "graphName": graph.name,
            "plan": strategy.to_dict(),
            "message": f"Strategy '{name}' saved successfully.",
        }

    @ai_function()
    async def load_strategy(
        self,
        strategy_id: Annotated[str, AIParam(desc="ID of strategy to load")],
    ) -> dict[str, Any]:
        """Load a previously saved strategy.

        This restores the strategy for viewing or modification.
        """
        # In production, this would load from database
        return self._tool_error(
            "NOT_IMPLEMENTED",
            "Strategy loading not yet implemented",
            strategyId=strategy_id,
        )

    @ai_function()
    async def list_saved_strategies(
        self,
        site_id: Annotated[str | None, AIParam(desc="Filter by site")] = None,
    ) -> list[dict[str, Any]]:
        """List the user's saved strategies.

        Returns a list of strategy summaries with names and dates.
        """
        # In production, this would query the database
        return []

    @ai_function()
    async def rename_strategy(
        self,
        new_name: Annotated[str, AIParam(desc="New name for the strategy")],
        description: Annotated[str, AIParam(desc="Strategy description")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to rename")] = None,
    ) -> dict[str, Any]:
        """Rename the current strategy."""
        graph = self.session.get_graph(graph_id)
        if not graph:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        if not graph.current_strategy:
            return self._tool_error(
                ErrorCode.INVALID_STRATEGY, "No strategy to rename."
            )

        old_name = graph.current_strategy.name
        graph.current_strategy.name = new_name
        graph.current_strategy.description = description
        graph.name = new_name
        graph.save_history(f"Renamed from '{old_name}' to '{new_name}'")

        return {
            "ok": True,
            "graphId": graph.id,
            "oldName": old_name,
            "newName": new_name,
            "name": new_name,
            "recordType": graph.current_strategy.record_type,
            "description": graph.current_strategy.description,
            "plan": graph.current_strategy.to_dict(),
        }

    @ai_function()
    async def clear_strategy(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to clear")] = None,
        confirm: Annotated[
            bool,
            AIParam(desc="Set true to confirm deleting all nodes in the graph"),
        ] = False,
    ) -> dict[str, Any]:
        """Clear the current strategy and start fresh.

        This removes all steps and the current strategy. Requires explicit confirmation.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        if not confirm:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Refusing to clear graph without confirmation. Use confirm=true or delete_graph.",
                graphId=graph.id,
                requiresConfirmation=True,
            )

        graph.steps.clear()
        graph.current_strategy = None
        graph.history.clear()
        graph.last_step_id = None

        return {
            "ok": True,
            "graphId": graph.id,
            "cleared": True,
            "message": "Strategy cleared. Ready to start fresh.",
        }

    @ai_function()
    async def delete_graph(
        self,
        graph_id: Annotated[str, AIParam(desc="Graph ID to delete")],
        confirm: Annotated[
            bool,
            AIParam(desc="Set true to confirm deleting the entire graph"),
        ] = False,
    ) -> dict[str, Any]:
        """Fully delete a graph from the current strategy session."""
        if not confirm:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Refusing to delete graph without confirmation.",
                graphId=graph_id,
                requiresConfirmation=True,
            )
        removed = self.session.remove_graph(graph_id)
        if not removed:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return {
            "ok": True,
            "graphId": graph_id,
            "graphDeleted": True,
        }

    @ai_function()
    async def get_strategy_summary(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to summarize")] = None,
    ) -> dict[str, Any]:
        """Get a summary of the current strategy.

        Returns step count, record type, and other metadata.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        if not graph.current_strategy:
            return {
                "hasStrategy": False,
                "graphId": graph.id,
                "graphName": graph.name,
                "stepCount": len(graph.steps),
                "message": (
                    f"No complete strategy yet. {len(graph.steps)} steps created."
                ),
            }

        strategy = graph.current_strategy
        return {
            "hasStrategy": True,
            "graphId": graph.id,
            "graphName": graph.name,
            "name": strategy.name,
            "recordType": strategy.record_type,
            "stepCount": len(strategy.get_all_steps()),
            "description": strategy.description,
        }

    @ai_function()
    async def get_edit_history(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to inspect")] = None,
    ) -> list[dict[str, Any]]:
        """Get the edit history of the current strategy.

        Shows what changes have been made during this session.
        """
        graph = self.session.get_graph(graph_id)
        if not graph:
            return [self._tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)]
        return [
            {"index": i, "description": h.get("description", "")}
            for i, h in enumerate(graph.history)
        ]

