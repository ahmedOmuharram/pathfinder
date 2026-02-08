"""Graph inspection tools (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Protocol, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.wdk_counts import compute_step_counts_for_plan
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
    ) -> JSONArray:
        """List all steps in the current strategy context.

        Shows what steps have been created and their relationships.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return [self._graph_not_found(graph_id)]
        steps: JSONArray = []
        for _, step in graph.steps.items():
            steps.append(self._serialize_step(graph, step))
        return steps

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

    @ai_function()
    async def get_draft_step_counts(
        self,
        graph_id: Annotated[
            str | None, AIParam(desc="Graph ID to compute counts for")
        ] = None,
    ) -> JSONObject:
        """Compute result counts for each draft step (WDK-backed, no build required).

        This compiles and executes the *current plan* in a temporary WDK strategy, then
        returns counts keyed by local step ID. Use this to detect 0-result steps early.
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        validation = await self.validate_graph_structure(graph_id=graph.id)
        if validation.get("ok") is not True:
            return {
                "ok": False,
                "code": "GRAPH_INVALID",
                "message": "Cannot compute counts until the graph validates as single-output.",
                "validation": validation,
            }

        root_ids_raw = validation.get("rootStepIds")
        root_ids = list(root_ids_raw if isinstance(root_ids_raw, list) else [])
        if len(root_ids) != 1:
            return {
                "ok": False,
                "code": "GRAPH_INVALID",
                "message": "Cannot compute counts without a single root step.",
                "validation": validation,
            }

        root_step = graph.get_step(root_ids[0])
        record_type = self._infer_record_type(root_step) if root_step else None
        if not root_step or not record_type:
            return self._tool_error(
                "COUNT_UNAVAILABLE",
                "Cannot compute counts: unable to infer record type for current output.",
                graphId=graph.id,
                rootStepId=root_ids[0] if root_ids else None,
            )

        strategy = StrategyAST(
            record_type=record_type,
            root=root_step,
            name=graph.name,
            description=getattr(graph.current_strategy, "description", None)
            if graph.current_strategy
            else None,
        )
        plan = strategy.to_dict()
        # Re-validate via the same path as HTTP endpoints to keep behavior consistent.
        strategy_ast = validate_plan_or_raise(plan)
        counts = await compute_step_counts_for_plan(
            plan, strategy_ast, self.session.site_id
        )
        zeros = sorted([step_id for step_id, count in counts.items() if count == 0])
        return {
            "ok": True,
            "graphId": graph.id,
            "graphName": graph.name,
            "rootStepId": root_ids[0],
            "counts": counts,
            "zeroStepIds": zeros,
            "zeroCount": len(zeros),
        }
