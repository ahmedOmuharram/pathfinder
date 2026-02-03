"""Editing tools for existing graph steps (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.domain.parameters.validation import validate_parameters
from veupath_chatbot.domain.strategy.ast import CombineStep, SearchStep, TransformStep
from veupath_chatbot.domain.strategy.ops import parse_op


class StrategyEditOps:
    """Tools that mutate existing steps/graph state."""

    @ai_function()
    async def delete_step(
        self,
        step_id: Annotated[str, AIParam(desc="ID of the step to delete")],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
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
                if isinstance(step, TransformStep) and step.input.id in to_remove:
                    to_remove.add(sid)
                    changed = True
                if isinstance(step, CombineStep) and (
                    step.left.id in to_remove or step.right.id in to_remove
                ):
                    to_remove.add(sid)
                    changed = True

        remaining = {sid for sid in graph.steps.keys() if sid not in to_remove}
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
        response = {"deleted": list(to_remove), "graphId": graph.id}
        return self._with_full_graph(graph, response)

    @ai_function()
    async def undo_last_change(
        self,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to undo")] = None,
    ) -> dict[str, Any]:
        """Undo the last change to the strategy."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)
        if graph.undo():
            return self._with_full_graph(
                graph,
                {"ok": True, "graphId": graph.id, "message": "Undone to previous state"},
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
    ) -> dict[str, Any]:
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
    async def update_combine_operator(
        self,
        step_id: Annotated[str, AIParam(desc="Combine step ID")],
        operator: Annotated[
            str,
            AIParam(desc="Operator: INTERSECT, UNION, MINUS_LEFT, MINUS_RIGHT, COLOCATE"),
        ],
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step or not isinstance(step, CombineStep):
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND,
                f"Combine step not found: {step_id}",
                stepId=step_id,
            )

        op = parse_op(operator)
        previous = step.op
        step.op = op
        if step.display_name in (None, previous.value):
            step.display_name = op.value

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

    @ai_function()
    async def update_step_parameters(
        self,
        step_id: Annotated[str, AIParam(desc="Step ID")],
        parameters: Annotated[dict[str, Any], AIParam(desc="Updated parameters for the step")],
        display_name: Annotated[str | None, AIParam(desc="Optional new display name")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        step = graph.get_step(step_id)
        if not step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND, f"Step not found: {step_id}", stepId=step_id
            )

        if isinstance(step, SearchStep):
            params = parameters
            try:
                await validate_parameters(
                    site_id=self.session.site_id,
                    record_type=step.record_type,
                    search_name=step.search_name,
                    parameters=params,
                    resolve_record_type_for_search=self._resolve_record_type_for_search,
                    find_record_type_hint=self._find_record_type_hint,
                    extract_vocab_options=self._extract_vocab_options,
                )
            except ValidationError as exc:
                return self._validation_error_payload(
                    exc, recordType=step.record_type, searchName=step.search_name
                )
            step.parameters = params
        elif isinstance(step, TransformStep):
            params = parameters
            record_type = self._infer_record_type(step)
            if not record_type:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Record type could not be inferred for transform.",
                )
            try:
                await validate_parameters(
                    site_id=self.session.site_id,
                    record_type=record_type,
                    search_name=step.transform_name,
                    parameters=params,
                    resolve_record_type_for_search=self._resolve_record_type_for_search,
                    find_record_type_hint=self._find_record_type_hint,
                    extract_vocab_options=self._extract_vocab_options,
                )
            except ValidationError as exc:
                return self._validation_error_payload(
                    exc, recordType=record_type, searchName=step.transform_name
                )
            step.parameters = params
        else:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Only search or transform steps can update parameters.",
            )

        if display_name:
            step.display_name = display_name

        response = self._serialize_step(graph, step)
        response["ok"] = True
        return self._with_full_graph(graph, response)

