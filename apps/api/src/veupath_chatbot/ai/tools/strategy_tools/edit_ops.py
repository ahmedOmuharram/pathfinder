"""Editing tools for existing graph steps (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.domain.parameters.validation import validate_parameters
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.strategy_tools.helpers import StrategyToolsHelpers


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
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND,
                f"Step not found: {step_id}",
                graphId=graph.id,
                stepId=step_id,
            )

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
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Deleting this step would remove all nodes. Use clear_strategy(confirm=true) to start over.",
                graphId=graph.id,
                requiresConfirmation=True,
            )

        for sid in to_remove:
            graph.steps.pop(sid, None)

        graph.current_strategy = None
        graph.last_step_id = next(iter(remaining), None)
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
            {"ok": False, "graphId": graph.id, "message": "Nothing to undo"},
        )

    @ai_function()
    async def rename_step(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID to rename")],
        new_name: Annotated[str, AIParam(desc="New display name")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Rename a step with a new display name."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        step.display_name = new_name

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_plan_payload(graph, response)

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
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        if not isinstance(step, PlanStepNode):
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Unsupported step object.",
                stepId=step_id,
            )

        if search_name:
            step.search_name = search_name

        if parameters is not None:
            # Only validate parameters for leaf steps. Input-bound questions often
            # have an input-step param that should not be provided by the model.
            if step.primary_input is None and step.secondary_input is None:
                record_type = graph.record_type or "gene"
                try:
                    await validate_parameters(
                        site_id=self.session.site_id,
                        record_type=record_type,
                        search_name=step.search_name,
                        parameters=parameters,
                        resolve_record_type_for_search=self._resolve_record_type_for_search,
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
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "operator can only be set for binary steps.",
                    stepId=step_id,
                )
            step.operator = parse_op(operator)

        if display_name:
            step.display_name = display_name

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)
