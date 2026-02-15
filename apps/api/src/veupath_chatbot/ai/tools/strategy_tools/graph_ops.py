"""Graph inspection tools (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Protocol, cast

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategy_tools.graph_integrity import (
    find_root_step_ids,
    validate_graph_integrity,
)
from veupath_chatbot.services.strategy_tools.helpers import StrategyToolsHelpers


class CreateStepProtocol(Protocol):
    """Protocol for classes that have a create_step method."""

    async def create_step(
        self,
        search_name: str | None = None,
        parameters: JSONObject | None = None,
        record_type: str | None = None,
        primary_input_step_id: str | None = None,
        secondary_input_step_id: str | None = None,
        operator: str | None = None,
        display_name: str | None = None,
        upstream: int | None = None,
        downstream: int | None = None,
        strand: str | None = None,
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
        for _, step in graph.steps.items():
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

        errors = [err.to_dict() for err in validate_graph_integrity(graph)]
        root_step_ids = find_root_step_ids(graph)

        ok = len(errors) == 0 and len(root_step_ids) == 1
        payload: JSONObject = {
            "ok": ok,
            "graphId": graph.id,
            "graphName": graph.name,
            "rootStepIds": cast(JSONArray, root_step_ids),
            "rootCount": len(root_step_ids),
            "errors": cast(JSONArray, errors),
            "graphSnapshot": self._build_graph_snapshot(graph),
        }
        if not ok:
            payload["code"] = "GRAPH_INVALID"
            payload["message"] = "Graph validation failed."
            if len(root_step_ids) > 1:
                payload["suggestedFix"] = cast(
                    JSONObject,
                    {
                        "action": "UNION_ROOTS",
                        "operator": "UNION",
                        "inputs": cast(JSONArray, root_step_ids),
                    },
                )
        return payload

    @ai_function()
    async def ensure_single_output(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to repair")] = None,
        operator: Annotated[
            str, AIParam(desc="Combine operator to use (default UNION)")
        ] = "UNION",
        display_name: Annotated[
            str | None, AIParam(desc="Optional display name for the final combine")
        ] = None,
    ) -> JSONObject:
        """Ensure the graph has exactly one output by combining roots (default UNION).

        If multiple roots exist, this chains combines until one root remains.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        validation = await self.validate_graph_structure(graph_id=graph.id)
        if validation.get("ok") is True:
            root_ids_raw = validation.get("rootStepIds")
            root_ids = root_ids_raw if isinstance(root_ids_raw, list) else []
            graph_snapshot = validation.get("graphSnapshot")
            return {
                "ok": True,
                "graphId": graph.id,
                "graphName": graph.name,
                "rootStepId": root_ids[0] if root_ids else None,
                "rootStepIds": root_ids,
                "graphSnapshot": graph_snapshot,
            }

        root_ids_raw = validation.get("rootStepIds")
        root_ids = list(root_ids_raw if isinstance(root_ids_raw, list) else [])
        if len(root_ids) == 0:
            # Return validation dict directly - it's already JSONObject
            result: JSONObject = validation
            return result
        if len(root_ids) == 1:
            graph_snapshot = validation.get("graphSnapshot")
            return {
                "ok": True,
                "graphId": graph.id,
                "graphName": graph.name,
                "rootStepId": root_ids[0],
                "rootStepIds": root_ids,
                "graphSnapshot": graph_snapshot,
            }

        current = root_ids[0]
        last_response: JSONObject | None = None
        for index, next_id in enumerate(root_ids[1:], start=1):
            is_final = index == len(root_ids) - 1
            # create_step is provided by StrategyStepOps via multiple inheritance in StrategyTools.
            # Cast to Protocol to satisfy type checker - this method exists at runtime via mixin.
            create_step_self = cast("CreateStepProtocol", self)
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
                    self._tool_error(
                        "ENSURE_SINGLE_OUTPUT_FAILED",
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
