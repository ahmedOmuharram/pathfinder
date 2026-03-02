"""Validation and error-payload helpers for strategy tools."""

from __future__ import annotations

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
            return self._tool_error(
                ErrorCode.NOT_FOUND, "Graph not found", graphId=graph_id
            )
        return self._tool_error(
            ErrorCode.NOT_FOUND, "Graph not found. Provide a graphId.", graphId=graph_id
        )

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
        return self._tool_error(ErrorCode.VALIDATION_ERROR, exc.title, **details)

    def _tool_error(
        self, code: ErrorCode | str, message: str, **details: JSONValue
    ) -> JSONObject:
        return tool_error(code, message, **details)

    def _is_placeholder_name(self, name: str | None) -> bool:
        if not name:
            return True
        return name.strip().lower() in {"draft graph", "draft strategy", "draft"}
