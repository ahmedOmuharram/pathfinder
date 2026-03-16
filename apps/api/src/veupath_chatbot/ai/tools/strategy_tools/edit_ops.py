"""Editing tools for existing graph steps (AI-exposed)."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.param_validation import validate_parameters
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
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)
        if step_id not in graph.steps:
            return self._step_not_found(step_id)

        to_remove = {step_id}
        changed = True
        while changed:
            changed = False
            for sid, step in list(graph.steps.items()):
                if sid in to_remove:
                    continue
                primary_id = getattr(getattr(step, "primary_input", None), "id", None)
                secondary_id = getattr(
                    getattr(step, "secondary_input", None), "id", None
                )
                if isinstance(primary_id, str) and primary_id in to_remove:
                    to_remove.add(sid)
                    changed = True
                if isinstance(secondary_id, str) and secondary_id in to_remove:
                    to_remove.add(sid)
                    changed = True

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

        graph.current_strategy = None
        graph.last_step_id = next(iter(remaining), None)
        # Recompute the subtree-root set after bulk removal.
        graph.recompute_roots()
        response: JSONObject = {
            "deleted": cast(JSONArray, list(to_remove)),
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
            tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Nothing to undo",
                graphId=graph.id,
            ),
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

        if search_name:
            step.search_name = search_name

        if parameters is not None:
            # Validate parameters for leaf steps (no inputs) and transform
            # steps (primary_input set, no secondary_input).  Binary combine
            # steps are structurally defined and have no WDK params to check.
            if step.secondary_input is None:
                record_type = graph.record_type or "transcript"
                try:
                    await validate_parameters(
                        site_id=self.session.site_id,
                        record_type=record_type,
                        search_name=step.search_name,
                        parameters=parameters,
                        resolve_record_type_for_search=self._find_record_type_for_search,
                        find_record_type_hint=self._find_record_type_hint,
                        extract_vocab_options=self._extract_vocab_options,
                    )
                except ValidationError as exc:
                    return self._validation_error_payload(
                        exc, recordType=record_type, searchName=step.search_name
                    )
            step.parameters = parameters

        if operator is not None:
            if step.secondary_input is None:
                return tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "operator can only be set for binary steps.",
                    stepId=step_id,
                )
            step.operator = parse_op(operator)

        if display_name:
            step.display_name = display_name

        return self._step_ok_response(graph, step)
