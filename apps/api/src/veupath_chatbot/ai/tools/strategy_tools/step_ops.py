"""Step creation tools (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.parameters.validation import validate_parameters
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp, ColocationParams, parse_op
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service

logger = get_logger(__name__)


class StrategyStepOps:
    """Tools that add new steps to a graph."""

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

        # Derive boolean question name for binary steps when not supplied.
        if secondary_input is not None and not search_name:
            search_name = f"boolean_question_{resolved_record_type}".strip("_") or "boolean_question"

        if not search_name:
            return self._tool_error(
                ErrorCode.INVALID_STRATEGY,
                "search_name is required for non-binary steps.",
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