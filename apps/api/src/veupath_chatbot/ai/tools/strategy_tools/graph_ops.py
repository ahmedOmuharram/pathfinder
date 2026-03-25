"""Graph inspection tools (AI-exposed)."""

from typing import Annotated, cast

from kani import AIParam, ai_function
from pydantic import Field

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategies.engine.graph_integrity import (
    find_root_step_ids,
    validate_graph_integrity,
)
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers

logger = get_logger(__name__)


class GraphValidationResult(CamelModel):
    """Typed result from ``validate_graph_structure``."""

    ok: bool
    graph_id: str
    graph_name: str
    root_step_ids: list[str]
    root_count: int
    errors: list[JSONObject] = Field(default_factory=list)
    graph_snapshot: JSONObject | None = None
    code: str | None = None
    message: str | None = None
    suggested_fix: JSONObject | None = None


class StrategyGraphOps(StrategyToolsHelpers):
    """Graph inspection tools."""

    @ai_function()
    async def list_current_steps(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to inspect")] = None,
    ) -> JSONObject:
        """List all steps in the current strategy graph.

        Returns graph metadata and per-step details including WDK step IDs
        and estimated result counts (when the strategy has been built).
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)
        steps: JSONArray = []
        for step in graph.steps.values():
            steps.append(self._serialize_step(graph, step))

        wdk_strategy_id_value: JSONValue = graph.wdk_strategy_id
        return {
            "graphId": graph.id,
            "graphName": graph.name,
            "recordType": graph.record_type,
            "wdkStrategyId": wdk_strategy_id_value,
            "isBuilt": graph.wdk_strategy_id is not None,
            "stepCount": len(steps),
            "steps": steps,
        }

    @ai_function()
    async def validate_graph_structure(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to validate")] = None,
    ) -> GraphValidationResult:
        """Validate that the working graph is structurally sound and has one output.

        This is a "done check" tool for the orchestrator. It verifies the single-output
        invariant (exactly one root) and detects broken references.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return GraphValidationResult(
                ok=False,
                graph_id=graph_id or "",
                graph_name="",
                root_step_ids=[],
                root_count=0,
                errors=[self._graph_not_found(graph_id)],
            )

        errors = [
            err.model_dump(by_alias=True, exclude_none=True, mode="json")
            for err in validate_graph_integrity(graph)
        ]
        root_step_ids = find_root_step_ids(graph)

        ok = len(errors) == 0 and len(root_step_ids) == 1
        result = GraphValidationResult(
            ok=ok,
            graph_id=graph.id,
            graph_name=graph.name,
            root_step_ids=root_step_ids,
            root_count=len(root_step_ids),
            errors=errors,
            graph_snapshot=self._build_graph_snapshot(graph),
        )
        if not ok:
            result.code = "GRAPH_INVALID"
            result.message = "Graph validation failed."
            if len(root_step_ids) > 1:
                result.suggested_fix = {
                    "action": "UNION_ROOTS",
                    "operator": "UNION",
                    "inputs": cast("JSONArray", root_step_ids),
                }

        return result

