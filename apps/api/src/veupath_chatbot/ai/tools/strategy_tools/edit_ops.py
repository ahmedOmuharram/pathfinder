"""Editing tools for existing graph steps (AI-exposed)."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.param_validation import (
    ValidationCallbacks,
    validate_parameters,
)
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers


class StrategyEditOps(StrategyToolsHelpers):
    """Tools that mutate existing steps/graph state."""

    @ai_function()
    async def delete_step(
        self,
        step_id: Annotated[str, AIParam(desc="ID of the step to delete")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Delete a step from the graph (and dependent steps)."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, _ = result

        to_remove = _find_dependent_steps(graph, step_id)
        remaining = {sid for sid in graph.steps if sid not in to_remove}
        if not remaining:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Deleting this step would remove all nodes. Use clear_strategy(confirm=true) to start over.",
                graphId=graph.id,
                requiresConfirmation=True,
            )

        for sid in to_remove:
            graph.steps.pop(sid, None)

        graph.invalidate_build()
        graph.last_step_id = next(iter(remaining), None)
        graph.recompute_roots()
        response: JSONObject = {
            "deleted": cast("JSONArray", list(to_remove)),
            "graphId": graph.id,
        }
        return self._with_full_graph(graph, response)

    @ai_function()
    async def undo_last_change(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to undo")] = None,
    ) -> JSONObject:
        """Undo the last change to the strategy."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)
        if graph.undo():
            return self._with_full_graph(
                graph,
                {
                    "ok": True,
                    "graphId": graph.id,
                    "message": "Undone to previous state",
                },
            )
        return self._with_full_graph(
            graph,
            tool_error(ErrorCode.VALIDATION_ERROR, "Nothing to undo", graphId=graph.id),
        )

    @ai_function()
    async def rename_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to rename")],
        new_name: Annotated[str, AIParam(desc="New display name")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Rename a step with a new display name."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, step = result

        step.display_name = new_name
        return self._step_ok_response(graph, step)

    async def _apply_step_updates(
        self,
        graph: object,
        step: PlanStepNode,
        search_name: str | None,
        parameters: JSONObject | None,
        operator: str | None,
        display_name: str | None,
    ) -> JSONObject | None:
        """Apply update fields to a step. Returns an error payload or None on success."""
        substantive_change = False

        if search_name:
            step.search_name = search_name
            substantive_change = True

        if parameters is not None:
            error = await self._validate_and_set_params(graph, step, parameters)
            if error is not None:
                return error
            substantive_change = True

        if operator is not None:
            error = self._validate_and_set_operator(step, step.id, operator)
            if error is not None:
                return error
            substantive_change = True

        if display_name:
            step.display_name = display_name

        if substantive_change:
            graph.invalidate_build()

        return None

    async def _get_plan_step(
        self, graph_id: str | None, step_id: str
    ) -> tuple[object, PlanStepNode] | JSONObject:
        """Resolve graph + step and assert step is a PlanStepNode."""
        result = self._get_graph_and_step(graph_id, step_id)
        if isinstance(result, dict):
            return result
        graph, step = result
        if not isinstance(step, PlanStepNode):
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Unsupported step object.",
                stepId=step_id,
            )
        return graph, step

    @ai_function()
    async def update_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID")],
        search_name: Annotated[
            str | None, AIParam(desc="Optional new WDK search/question name")
        ] = None,
        parameters: Annotated[
            JSONObject | None, AIParam(desc="Optional new parameters object")
        ] = None,
        operator: Annotated[
            str | None,
            AIParam(desc="Optional new operator (only applies to binary steps)"),
        ] = None,
        display_name: Annotated[
            str | None, AIParam(desc="Optional new display name")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Update an existing strategy step's search, parameters, operator, or display name."""
        resolved = await self._get_plan_step(graph_id, step_id)
        if isinstance(resolved, dict):
            return resolved
        graph, step = resolved

        apply_error = await self._apply_step_updates(
            graph, step, search_name, parameters, operator, display_name
        )
        return (
            apply_error
            if apply_error is not None
            else self._step_ok_response(graph, step)
        )

    async def _validate_and_set_params(
        self,
        graph: object,
        step: PlanStepNode,
        parameters: JSONObject,
    ) -> JSONObject | None:
        """Validate and set parameters on a step. Returns error or None."""
        if step.secondary_input is not None:
            step.parameters = parameters
            return None
        record_type = graph.record_type or "transcript"
        try:
            await validate_parameters(
                SearchContext(self.session.site_id, record_type, step.search_name),
                parameters=parameters,
                callbacks=ValidationCallbacks(
                    resolve_record_type_for_search=self._find_record_type_for_search,
                    find_record_type_hint=self._find_record_type_hint,
                    extract_vocab_options=self._extract_vocab_options,
                ),
            )
        except ValidationError as exc:
            return self._validation_error_payload(
                exc, recordType=record_type, searchName=step.search_name
            )
        step.parameters = parameters
        return None

    def _validate_and_set_operator(
        self,
        step: PlanStepNode,
        step_id: str,
        operator: str,
    ) -> JSONObject | None:
        """Validate and set operator on a binary step. Returns error or None."""
        if step.secondary_input is None:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "operator can only be set for binary steps.",
                stepId=step_id,
            )
        step.operator = parse_op(operator)
        return None


def _find_dependent_steps(graph: object, step_id: str) -> set[str]:
    """Find all steps transitively dependent on the given step."""
    to_remove = {step_id}
    changed = True
    while changed:
        changed = False
        for sid, step in list(graph.steps.items()):
            if sid in to_remove:
                continue
            primary_id = getattr(getattr(step, "primary_input", None), "id", None)
            secondary_id = getattr(getattr(step, "secondary_input", None), "id", None)
            if isinstance(primary_id, str) and primary_id in to_remove:
                to_remove.add(sid)
                changed = True
            if isinstance(secondary_id, str) and secondary_id in to_remove:
                to_remove.add(sid)
                changed = True
    return to_remove
