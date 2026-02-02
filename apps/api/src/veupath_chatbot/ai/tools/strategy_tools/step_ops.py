"""Step creation tools (AI-exposed)."""

from __future__ import annotations

from typing import Annotated, Any

from kani import AIParam, ai_function

from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.parameters.validation import validate_parameters
from veupath_chatbot.domain.strategy.ast import CombineStep, SearchStep, TransformStep
from veupath_chatbot.domain.strategy.ops import CombineOp, ColocationParams, parse_op
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service

logger = get_logger(__name__)


class StrategyStepOps:
    """Tools that add new steps to a graph."""

    @ai_function()
    async def create_search_step(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (e.g., 'gene')")],
        search_name: Annotated[str, AIParam(desc="Name of the search")],
        parameters: Annotated[
            dict[str, Any] | None,
            AIParam(desc="Search parameters as key-value pairs (optional)"),
        ] = None,
        display_name: Annotated[
            str | None,
            AIParam(desc="Optional friendly name for this step"),
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Create a new search step."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        resolved_record_type = await self._resolve_record_type_for_search(
            record_type, search_name, require_match=True, allow_fallback=False
        )
        if resolved_record_type is None:
            record_type_hint = await self._find_record_type_hint(
                search_name, exclude=record_type
            )
            return self._tool_error(
                ErrorCode.SEARCH_NOT_FOUND,
                f"Unknown or invalid search: {search_name}",
                recordType=record_type,
                recordTypeHint=record_type_hint,
                detail="Search name not found in any record type.",
            )
        record_type = resolved_record_type
        parameters = parameters or {}

        discovery = get_discovery_service()
        try:
            details = await discovery.get_search_details(
                self.session.site_id, record_type, search_name
            )
            search_data = (
                details.get("searchData", details) if isinstance(details, dict) else {}
            )
            param_specs = (
                search_data.get("parameters", []) if isinstance(search_data, dict) else []
            )
            input_param = next(
                (p for p in param_specs if p.get("type") == "input-step"), None
            )
            if input_param:
                return self._tool_error(
                    ErrorCode.INVALID_PARAMETERS,
                    "Search requires an input step; use transform_step.",
                    recordType=record_type,
                    searchName=search_name,
                    inputParam=input_param.get("name"),
                    suggestion="Use transform_step or find_orthologs with input_step_id.",
                    example={
                        "tool": "transform_step",
                        "input_step_id": "<step_id>",
                        "transform_name": search_name,
                        "parameters": {input_param.get("name"): "<step_id>"},
                    },
                )
        except Exception as exc:
            logger.warning(
                "Failed to inspect search details for input-step params",
                record_type=record_type,
                search_name=search_name,
                error=str(exc),
            )

        try:
            await validate_parameters(
                site_id=self.session.site_id,
                record_type=record_type,
                search_name=search_name,
                parameters=parameters,
                resolve_record_type_for_search=self._resolve_record_type_for_search,
                find_record_type_hint=self._find_record_type_hint,
                extract_vocab_options=self._extract_vocab_options,
            )
        except ValidationError as exc:
            return self._validation_error_payload(
                exc, recordType=record_type, searchName=search_name
            )

        step = SearchStep(
            record_type=record_type,
            search_name=search_name,
            parameters=parameters,
            display_name=display_name or search_name,
        )

        step_id = graph.add_step(step)

        logger.info("Created search step", step_id=step_id, search=search_name)
        response = self._serialize_step(graph, step)
        return self._with_full_graph(graph, response)

    @ai_function()
    async def combine_steps(
        self,
        left_step_id: Annotated[str, AIParam(desc="ID of the left/primary step")],
        right_step_id: Annotated[str, AIParam(desc="ID of the right/secondary step")],
        operator: Annotated[
            str,
            AIParam(
                desc="Operator: INTERSECT (AND), UNION (OR), MINUS_LEFT, MINUS_RIGHT, or COLOCATE"
            ),
        ],
        display_name: Annotated[str | None, AIParam(desc="Optional name")] = None,
        upstream: Annotated[int | None, AIParam(desc="Upstream bp for COLOCATE")] = None,
        downstream: Annotated[
            int | None, AIParam(desc="Downstream bp for COLOCATE")
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Combine two steps with a set operation."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        left_step = graph.get_step(left_step_id)
        right_step = graph.get_step(right_step_id)

        missing = []
        if not left_step:
            missing.append(left_step_id)
        if not right_step:
            missing.append(right_step_id)
        if missing:
            return self._with_full_graph(
                graph,
                self._tool_error(
                    ErrorCode.STEP_NOT_FOUND,
                    "Combine requires two existing steps.",
                    missingStepIds=missing,
                    graphId=graph.id,
                ),
            )

        left_type = self._infer_record_type(left_step)
        right_type = self._infer_record_type(right_step)
        if left_type and right_type and left_type != right_type:
            return self._with_full_graph(
                graph,
                self._tool_error(
                    ErrorCode.INCOMPATIBLE_STEPS,
                    "Cannot combine steps with different record types.",
                    leftStepId=left_step_id,
                    leftRecordType=left_type,
                    rightStepId=right_step_id,
                    rightRecordType=right_type,
                    detail="Transform one side to match the other record type before combining.",
                    graphId=graph.id,
                ),
            )

        op = parse_op(operator)

        colocation = None
        if op == CombineOp.COLOCATE:
            colocation = ColocationParams(
                upstream=upstream or 0,
                downstream=downstream or 0,
            )

        step = CombineStep(
            op=op,
            left=left_step,
            right=right_step,
            display_name=display_name,
            colocation_params=colocation,
        )

        step_id = graph.add_step(step)

        logger.info("Created combine step", step_id=step_id, operator=op.value)
        response = self._serialize_step(graph, step)
        response["displayName"] = display_name or step.display_name or f"{op.value} result"
        return self._with_full_graph(graph, response)

    @ai_function()
    async def transform_step(
        self,
        input_step_id: Annotated[str, AIParam(desc="ID of the input step")],
        transform_name: Annotated[
            str, AIParam(desc="Transform name (e.g., 'GenesByOrthology')")
        ],
        parameters: Annotated[
            dict[str, Any] | None,
            AIParam(desc="Transform parameters"),
        ] = None,
        display_name: Annotated[str | None, AIParam(desc="Optional name")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Apply a transform to a step's results."""
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        input_step = graph.get_step(input_step_id)
        if not input_step:
            return self._tool_error(
                ErrorCode.STEP_NOT_FOUND,
                f"Step not found: {input_step_id}",
                stepId=input_step_id,
            )

        record_type = self._infer_record_type(input_step)
        if not record_type:
            return self._tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Unable to infer record type for transform step.",
            )

        parameters = parameters or {}

        discovery = get_discovery_service()
        try:
            details = await discovery.get_search_details(
                self.session.site_id, record_type, transform_name
            )
        except Exception as e:
            searches = await discovery.get_searches(self.session.site_id, record_type)
            candidates = self._filter_search_options(searches, "ortholog")
            available = [s.get("name") or s.get("urlSegment") for s in searches]
            return self._tool_error(
                ErrorCode.SEARCH_NOT_FOUND,
                f"Unknown or invalid transform: {transform_name}",
                recordType=record_type,
                availableTransforms=candidates or [s for s in available if s],
                detail=str(e),
            )

        param_specs = details.get("searchData", {}).get("parameters", [])
        required_params = [
            p for p in param_specs if not p.get("allowEmptyValue", True)
        ]

        missing = []
        for param in required_params:
            name = param.get("name")
            if not name:
                continue
            value = parameters.get(name)
            if value in (None, "", [], {}):
                missing.append(name)

        if missing:
            return self._tool_error(
                ErrorCode.INVALID_PARAMETERS,
                "Missing required parameters",
                recordType=record_type,
                transformName=transform_name,
                missing=missing,
            )

        step = TransformStep(
            transform_name=transform_name,
            input=input_step,
            parameters=parameters,
            display_name=display_name,
        )

        step_id = graph.add_step(step)

        logger.info("Created transform step", step_id=step_id, transform=transform_name)
        response = self._serialize_step(graph, step)
        response["displayName"] = display_name or step.display_name or transform_name
        return self._with_full_graph(graph, response)

    @ai_function()
    async def find_orthologs(
        self,
        input_step_id: Annotated[str, AIParam(desc="ID of the input gene step")],
        target_organisms: Annotated[list[str] | str, AIParam(desc="Target organism names")],
        is_syntenic: Annotated[str | bool | None, AIParam(desc="Filter by synteny: 'yes' or 'no'")] = None,
        display_name: Annotated[str | None, AIParam(desc="Optional name")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> dict[str, Any]:
        """Find orthologs for genes in a step using an orthology transform."""
        parameters: dict[str, Any] = {"organism": target_organisms}
        if is_syntenic is not None:
            if isinstance(is_syntenic, bool):
                parameters["isSyntenic"] = "yes" if is_syntenic else "no"
            elif isinstance(is_syntenic, str):
                normalized = is_syntenic.strip().lower()
                if normalized in {"true", "t", "yes", "y", "1"}:
                    parameters["isSyntenic"] = "yes"
                elif normalized in {"false", "f", "no", "n", "0"}:
                    parameters["isSyntenic"] = "no"
                else:
                    parameters["isSyntenic"] = is_syntenic
            else:
                parameters["isSyntenic"] = str(is_syntenic)
        return await self.transform_step(
            input_step_id=input_step_id,
            transform_name="GenesByOrthologs",
            parameters=parameters,
            display_name=display_name,
            graph_id=graph_id,
        )

