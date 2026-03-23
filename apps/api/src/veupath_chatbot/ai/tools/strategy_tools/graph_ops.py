"""Graph inspection tools (AI-exposed)."""

from typing import Annotated, Protocol, cast

from kani import AIParam, ai_function

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


class CreateStepProtocol(Protocol):
    """Protocol for the subset of create_step used by ensure_single_output.

    Only the fields called in :meth:`_chain_combines` are required here.
    """

    async def create_step(
        self,
        *,
        primary_input_step_id: str | None = None,
        secondary_input_step_id: str | None = None,
        operator: str | None = None,
        display_name: str | None = None,
        graph_id: str | None = None,
    ) -> JSONObject:
        """Create a step in the graph."""
        ...


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
    ) -> JSONObject:
        """Validate that the working graph is structurally sound and has one output.

        This is a "done check" tool for the orchestrator. It verifies the single-output
        invariant (exactly one root) and detects broken references.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        errors = [
            err.model_dump(by_alias=True, exclude_none=True, mode="json")
            for err in validate_graph_integrity(graph)
        ]
        root_step_ids = find_root_step_ids(graph)

        ok = len(errors) == 0 and len(root_step_ids) == 1
        payload: JSONObject = {
            "ok": ok,
            "graphId": graph.id,
            "graphName": graph.name,
            "rootStepIds": cast("JSONArray", root_step_ids),
            "rootCount": len(root_step_ids),
            "errors": cast("JSONArray", errors),
            "graphSnapshot": self._build_graph_snapshot(graph),
        }
        if not ok:
            payload["code"] = "GRAPH_INVALID"
            payload["message"] = "Graph validation failed."
            if len(root_step_ids) > 1:
                payload["suggestedFix"] = cast(
                    "JSONObject",
                    {
                        "action": "UNION_ROOTS",
                        "operator": "UNION",
                        "inputs": cast("JSONArray", root_step_ids),
                    },
                )

        return payload

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
        root_ids_raw = validation.get("rootStepIds")
        root_ids = list(root_ids_raw if isinstance(root_ids_raw, list) else [])
        if validation.get("ok") is True or len(root_ids) <= 1:
            return _build_single_output_response(graph, validation)

        return await self._chain_combines(
            graph=graph,
            root_ids=root_ids,
            operator=operator,
            display_name=display_name,
        )

    async def _chain_combines(
        self,
        *,
        graph: object,
        root_ids: list[JSONValue],
        operator: str,
        display_name: str | None,
    ) -> JSONObject:
        """Chain binary combines to reduce multiple roots to one."""
        current = root_ids[0]
        for index, next_id in enumerate(root_ids[1:], start=1):
            is_final = index == len(root_ids) - 1
            create_step_self = cast("CreateStepProtocol", cast("object", self))
            last_response = await create_step_self.create_step(
                primary_input_step_id=current,
                secondary_input_step_id=next_id,
                operator=str(operator),
                display_name=(display_name or "Combined output") if is_final else None,
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
        root_step_ids_raw = final_validation.get("rootStepIds")
        root_step_ids = root_step_ids_raw if isinstance(root_step_ids_raw, list) else []
        graph_snapshot = final_validation.get("graphSnapshot")
        return {
            "ok": final_validation.get("ok") is True,
            "graphId": graph.id,
            "graphName": graph.name,
            "rootStepId": current,
            "rootStepIds": root_step_ids,
            "graphSnapshot": graph_snapshot,
            "validation": final_validation,
        }


def _build_single_output_response(graph: object, validation: JSONObject) -> JSONObject:
    """Build response when graph already has a single output or no roots."""
    root_ids_raw = validation.get("rootStepIds")
    root_ids = root_ids_raw if isinstance(root_ids_raw, list) else []
    graph_snapshot = validation.get("graphSnapshot")
    if not root_ids:
        return validation
    return {
        "ok": True,
        "graphId": graph.id,
        "graphName": graph.name,
        "rootStepId": root_ids[0] if root_ids else None,
        "rootStepIds": root_ids,
        "graphSnapshot": graph_snapshot,
    }
