"""Graph inspection tools (AI-exposed)."""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers

logger = get_logger(__name__)



class StrategyGraphOps(StrategyToolsHelpers):
    """Graph inspection tools."""

    @ai_function()
    async def get_strategy(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to inspect")] = None,
        *,
        summary_only: Annotated[
            bool,
            AIParam(desc="If true (default), return only metadata. Set false for full step details."),
        ] = True,
    ) -> JSONObject:
        """Get the current strategy graph — summary metadata or full step details.

        By default returns a lightweight summary (step count, record type, build status).
        Pass summary_only=false for per-step details including WDK step IDs and estimated
        result counts.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        wdk_strategy_id_value: JSONValue = graph.wdk_strategy_id
        result: JSONObject = {
            "graphId": graph.id,
            "graphName": graph.name,
            "recordType": graph.record_type,
            "wdkStrategyId": wdk_strategy_id_value,
            "isBuilt": graph.wdk_strategy_id is not None,
            "stepCount": len(graph.steps),
            "description": graph.description,
        }

        if not summary_only:
            steps: JSONArray = []
            for step in graph.steps.values():
                steps.append(self._serialize_step(graph, step))
            result["steps"] = steps

        return result


