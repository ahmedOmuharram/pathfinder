"""Validation and error-payload helpers for strategy tools."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue

from .base import StrategyToolsBase


class ValidationMixin(StrategyToolsBase):
    def _get_graph(self, graph_id: str | None) -> StrategyGraph | None:
        graph = self.session.get_graph(graph_id)
        if graph:
            return graph
        # Fallback to active graph if an invalid id was provided.
        return self.session.get_graph(None)

    def _graph_not_found(self, graph_id: str | None) -> JSONObject:
        if graph_id:
            return tool_error(ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id)
        return tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

    def _step_not_found(self, step_id: str) -> JSONObject:
        """Standard error payload for a missing step."""
        return tool_error(
            ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
        )

    def _get_graph_and_step(
        self, graph_id: str | None, step_id: str
    ) -> tuple[StrategyGraph, PlanStepNode] | JSONObject:
        """Look up graph and step, returning an error dict on failure.

        Callers should check ``isinstance(result, dict)`` -- if True the
        result is a ready-to-return error payload.  Otherwise it is a
        ``(graph, step)`` tuple.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)
        step = graph.get_step(step_id)
        if not step:
            return self._step_not_found(step_id)
        return graph, step

    def _validation_error_payload(
        self, exc: ValidationError, **context: JSONValue
    ) -> JSONObject:
        details: JSONObject = {}
        if exc.detail:
            details["detail"] = exc.detail
        if exc.errors is not None:
            details["errors"] = exc.errors
            for error in exc.errors:
                if not isinstance(error, dict):
                    continue
                extra = error.get("context")
                if isinstance(extra, dict):
                    context.update({k: v for k, v in extra.items() if v is not None})
        details.update({k: v for k, v in context.items() if v is not None})
        return tool_error(ErrorCode.VALIDATION_ERROR, exc.title, **details)

    def _is_placeholder_name(self, name: str | None) -> bool:
        if not name:
            return True
        return name.strip().lower() in {
            "draft graph",
            "draft strategy",
            "draft",
            "new conversation",
        }
