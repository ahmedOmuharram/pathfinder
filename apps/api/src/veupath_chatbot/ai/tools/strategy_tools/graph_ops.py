"""Graph inspection tools (AI-exposed)."""

from typing import Annotated, cast

from kani import AIParam, ai_function
from pydantic import BaseModel, ConfigDict, Field

from veupath_chatbot.ai.tools.strategy_tools.step_ops import StepInputSpec
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategies.engine.graph_integrity import (
    find_root_step_ids,
    validate_graph_integrity,
)
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers

logger = get_logger(__name__)


class GraphValidationResult(BaseModel):
    """Typed result from ``validate_graph_structure``."""

    model_config = ConfigDict(populate_by_name=True)

    ok: bool
    graph_id: str = Field(alias="graphId")
    graph_name: str = Field(alias="graphName")
    root_step_ids: list[str] = Field(alias="rootStepIds")
    root_count: int = Field(alias="rootCount")
    errors: list[JSONObject] = Field(default_factory=list)
    graph_snapshot: JSONObject | None = Field(default=None, alias="graphSnapshot")
    code: str | None = None
    message: str | None = None
    suggested_fix: JSONObject | None = Field(default=None, alias="suggestedFix")


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
                graphId=graph_id or "",
                graphName="",
                rootStepIds=[],
                rootCount=0,
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
            graphId=graph.id,
            graphName=graph.name,
            rootStepIds=root_step_ids,
            rootCount=len(root_step_ids),
            errors=errors,
            graphSnapshot=self._build_graph_snapshot(graph),
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

    @ai_function()
    async def ensure_single_output(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to repair")] = None,
        operator: Annotated[
            str,
            AIParam(
                desc=(
                    "Combine operator to merge orphan roots. Default INTERSECT "
                    "because most strategies are filter chains where each step "
                    "narrows the result. Use UNION only when you intentionally "
                    "want to broaden results (e.g., combining alternative "
                    "identification methods like text search + GO term)."
                )
            ),
        ] = "INTERSECT",
        display_name: Annotated[
            str | None, AIParam(desc="Optional display name for the final combine")
        ] = None,
    ) -> JSONObject:
        """Ensure the graph has exactly one output by combining orphan roots.

        If multiple roots exist, chains combines until one root remains.
        Default operator is INTERSECT (most strategies are filter chains).
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        validation = await self.validate_graph_structure(graph_id=graph.id)
        if validation.ok or len(validation.root_step_ids) <= 1:
            return _build_single_output_response(graph, validation)

        return await self._chain_combines(
            graph=graph,
            root_ids=validation.root_step_ids,
            operator=operator,
            display_name=display_name,
        )

    async def _chain_combines(
        self,
        *,
        graph: StrategyGraph,
        root_ids: list[str],
        operator: str,
        display_name: str | None,
    ) -> JSONObject:
        """Chain binary combines to reduce multiple roots to one."""
        current: str = root_ids[0]
        for index, next_id in enumerate(root_ids[1:], start=1):
            is_final = index == len(root_ids) - 1
            last_response = await self.create_step(
                inputs=StepInputSpec(
                    primary_input_step_id=current,
                    secondary_input_step_id=next_id,
                    operator=operator,
                    display_name=(display_name or "Combined output") if is_final else None,
                ),
                graph_id=graph.id,
            )
            if (
                not isinstance(last_response, dict)
                or last_response.get("ok") is False
                or last_response.get("error")
            ):
                return self._with_full_graph(
                    graph,
                    tool_error(
                        ErrorCode.ENSURE_SINGLE_OUTPUT_FAILED,
                        "Failed while combining roots to ensure a single output.",
                        operator=operator,
                        leftStepId=current,
                        rightStepId=next_id,
                        response=last_response,
                    ),
                )
            current = str(last_response.get("stepId") or current)

        final_validation = await self.validate_graph_structure(graph_id=graph.id)
        return {
            "ok": final_validation.ok,
            "graphId": graph.id,
            "graphName": graph.name,
            "rootStepId": current,
            "rootStepIds": final_validation.root_step_ids,
            "graphSnapshot": final_validation.graph_snapshot,
            "validation": final_validation.model_dump(by_alias=True, exclude_none=True),
        }


def _build_single_output_response(
    graph: StrategyGraph, validation: GraphValidationResult
) -> JSONObject:
    """Build response when graph already has a single output or no roots."""
    if not validation.root_step_ids:
        return validation.model_dump(by_alias=True, exclude_none=True)
    return {
        "ok": True,
        "graphId": graph.id,
        "graphName": graph.name,
        "rootStepId": validation.root_step_ids[0],
        "rootStepIds": validation.root_step_ids,
        "graphSnapshot": validation.graph_snapshot,
    }
