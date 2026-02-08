"""Step creation tools (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.parameters.validation import validate_parameters
from veupath_chatbot.domain.parameters.specs import adapt_param_specs, find_input_step_param
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp, ColocationParams, parse_op
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client

logger = get_logger(__name__)


class StrategyStepOps:
    """Tools that add new steps to a graph."""

    _COMBINE_PLACEHOLDER_SEARCH_NAME = "__combine__"

    def _coerce_wdk_boolean_question_params(
        self,
        *,
        parameters: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        """Extract left/right/operator from WDK boolean-question parameter conventions.

        WDK boolean questions sometimes encode combines as a "boolean_question_*" search with
        parameters like:
          - bq_left_op_<...>: <stepId>
          - bq_right_op_<...>: <stepId>
          - bq_operator: UNION|INTERSECT|MINUS|...

        Our graph model represents combines structurally (primary/secondary/operator), so we
        translate these WDK-style parameters to the structural representation and strip the
        WDK boolean keys from `parameters`.
        """
        if not isinstance(parameters, dict) or not parameters:
            return None, None, None

        left_id: str | None = None
        right_id: str | None = None
        op: str | None = None

        for k, v in list(parameters.items()):
            key = str(k)
            if left_id is None and key.startswith("bq_left_op"):
                if v is not None:
                    left_id = str(v)
                parameters.pop(k, None)
                continue
            if right_id is None and key.startswith("bq_right_op"):
                if v is not None:
                    right_id = str(v)
                parameters.pop(k, None)
                continue

        # operator can be provided as bq_operator; strip it from params in favor of structural operator
        if "bq_operator" in parameters:
            raw = parameters.pop("bq_operator", None)
            if raw is not None:
                op = str(raw)

        if left_id and right_id and op:
            return left_id, right_id, op
        return None, None, None

    @ai_function()
    async def create_step(
        self,
        search_name: Annotated[
            str | None,
            AIParam(
                desc="WDK question/search name (required unless creating a binary step with operator)"
            ),
        ] = None,
        parameters: Annotated[
            dict[str, Any] | None,
            AIParam(desc="WDK parameters as key-value pairs (optional)"),
        ] = None,
        record_type: Annotated[
            str | None,
            AIParam(
                desc="Record type context (e.g., 'gene'). If omitted, the tool will try to infer it from the graph or discovery."
            ),
        ] = None,
        primary_input_step_id: Annotated[
            str | None, AIParam(desc="Primary input step id (optional)")
        ] = None,
        secondary_input_step_id: Annotated[
            str | None, AIParam(desc="Secondary input step id (optional)")
        ] = None,
        operator: Annotated[
            str | None,
            AIParam(desc="Set operator for binary steps (required if secondary_input_step_id is set)"),
        ] = None,
        display_name: Annotated[
            str | None,
            AIParam(desc="Optional friendly name for this step"),
        ] = None,
        upstream: Annotated[int | None, AIParam(desc="Upstream bp for COLOCATE")] = None,
        downstream: Annotated[int | None, AIParam(desc="Downstream bp for COLOCATE")] = None,
        strand: Annotated[
            str | None, AIParam(desc="Strand for COLOCATE: same|opposite|both")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Create a new strategy step.

        This is the single step-construction API. Step kind is inferred from structure:
        - leaf step: no inputs
        - unary step: primary_input_step_id only
        - binary step: primary_input_step_id + secondary_input_step_id (+ operator)
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        parameters = parameters or {}

        # WDK compatibility: if caller encoded a boolean combine as WDK boolean-question parameters,
        # translate it into structural inputs so the UI renders it as a UNION/INTERSECT/MINUS step.
        if not primary_input_step_id and not secondary_input_step_id and not operator:
            left, right, op = self._coerce_wdk_boolean_question_params(parameters=parameters)
            if left and right and op:
                primary_input_step_id = left
                secondary_input_step_id = right
                operator = op

        primary_input = None
        secondary_input = None
        if primary_input_step_id:
            primary_input = graph.get_step(primary_input_step_id)
            if not primary_input:
                return self._tool_error(
                    ErrorCode.STEP_NOT_FOUND,
                    "Primary input step not found.",
                    graphId=graph.id,
                    stepId=primary_input_step_id,
                )
        if secondary_input_step_id:
            secondary_input = graph.get_step(secondary_input_step_id)
            if not secondary_input:
                return self._tool_error(
                    ErrorCode.STEP_NOT_FOUND,
                    "Secondary input step not found.",
                    graphId=graph.id,
                    stepId=secondary_input_step_id,
                )
            if primary_input is None:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "secondary_input_step_id requires primary_input_step_id.",
                    graphId=graph.id,
                )
            if not operator:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "operator is required when secondary_input_step_id is provided.",
                    graphId=graph.id,
                )

        # Establish best-effort record type context for graph.
        resolved_record_type = graph.record_type or record_type
        if resolved_record_type is None and search_name:
            resolved_record_type = await self._resolve_record_type_for_search(
                None, search_name, require_match=False, allow_fallback=True
            )
        if resolved_record_type is None:
            resolved_record_type = "gene"
        graph.record_type = resolved_record_type

        # search_name is required for leaf and unary steps, but binary (combine) steps
        # are structurally defined by primary + secondary inputs + operator.
        is_binary = primary_input is not None and secondary_input is not None
        if not search_name:
            if is_binary:
                search_name = self._COMBINE_PLACEHOLDER_SEARCH_NAME
            else:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "search_name is required for leaf and transform steps.",
                    graphId=graph.id,
                )

        # Validate parameters only for leaf steps (input-bound questions often have input-step params).
        if primary_input is None and secondary_input is None:
            # Resolve record type to the record type that actually owns this WDK search.
            rt = await self._resolve_record_type_for_search(
                resolved_record_type, search_name, require_match=True, allow_fallback=True
            )
            if rt is None:
                record_type_hint = await self._find_record_type_hint(
                    search_name, exclude=resolved_record_type
                )
                return self._tool_error(
                    ErrorCode.SEARCH_NOT_FOUND,
                    f"Unknown or invalid search: {search_name}",
                    recordType=resolved_record_type,
                    recordTypeHint=record_type_hint,
                )
            graph.record_type = rt
            try:
                await validate_parameters(
                    site_id=self.session.site_id,
                    record_type=rt,
                    search_name=search_name,
                    parameters=parameters,
                    resolve_record_type_for_search=self._resolve_record_type_for_search,
                    find_record_type_hint=self._find_record_type_hint,
                    extract_vocab_options=self._extract_vocab_options,
                )
            except ValidationError as exc:
                return self._validation_error_payload(
                    exc, recordType=rt, searchName=search_name
                )

        # Validate transform steps too.
        #
        # The model can create a "transform" node structurally (primary_input_step_id set)
        # with a WDK question that does NOT accept an input step (no input-step AnswerParam). WDK then
        # rejects strategy creation with: "Step <id> does not allow a primary input step."
        #
        # We detect and reject these at creation time so invalid plans cannot be persisted.
        if primary_input is not None and secondary_input is None:
            rt = await self._resolve_record_type_for_search(
                resolved_record_type, search_name, require_match=True, allow_fallback=True
            )
            if rt is None:
                record_type_hint = await self._find_record_type_hint(
                    search_name, exclude=resolved_record_type
                )
                return self._tool_error(
                    ErrorCode.SEARCH_NOT_FOUND,
                    f"Unknown or invalid search: {search_name}",
                    recordType=resolved_record_type,
                    recordTypeHint=record_type_hint,
                )
            graph.record_type = rt

            # Validate parameters against WDK specs (required params, types, extra keys).
            try:
                await validate_parameters(
                    site_id=self.session.site_id,
                    record_type=rt,
                    search_name=search_name,
                    parameters=parameters,
                    resolve_record_type_for_search=self._resolve_record_type_for_search,
                    find_record_type_hint=self._find_record_type_hint,
                    extract_vocab_options=self._extract_vocab_options,
                )
            except ValidationError as exc:
                return self._validation_error_payload(
                    exc, recordType=rt, searchName=search_name
                )

            # Confirm the question supports an input step.
            try:
                wdk = get_wdk_client(self.session.site_id)
                details = await wdk.get_search_details(rt, search_name, expand_params=True)
            except Exception as exc:
                return self._tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "Failed to load search metadata for transform validation.",
                    recordType=rt,
                    searchName=search_name,
                    detail=str(exc),
                )
            if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
                details = details["searchData"]
            specs = adapt_param_specs(details if isinstance(details, dict) else {})
            input_param = find_input_step_param(specs)
            if not input_param:
                return self._tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    f"Search '{search_name}' cannot be used as a transform: it does not accept an input step.",
                    recordType=rt,
                    searchName=search_name,
                    suggestedFix={
                        "message": "Create this as a leaf step (no primary input) and then combine with the upstream step using INTERSECT/UNION/MINUS.",
                        "asLeaf": {"searchName": search_name, "recordType": rt},
                    },
                )

        op = parse_op(operator) if secondary_input is not None and operator else None
        colocation = None
        if op == CombineOp.COLOCATE:
            colocation = ColocationParams(
                upstream=upstream or 0,
                downstream=downstream or 0,
                strand=(strand or "both"),  # type: ignore[arg-type]
            )

        step = PlanStepNode(
            search_name=search_name,
            parameters=parameters,
            primary_input=primary_input,
            secondary_input=secondary_input,
            operator=op,
            colocation_params=colocation,
            display_name=display_name or search_name,
        )

        step_id = graph.add_step(step)

        logger.info("Created step", step_id=step_id, search=search_name)
        response = self._serialize_step(graph, step)
        return self._with_full_graph(graph, response)