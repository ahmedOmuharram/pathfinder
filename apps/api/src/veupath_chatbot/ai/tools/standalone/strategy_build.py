"""Standalone strategy build tools (leaf, combine, transform) for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
mixin-based tools exactly.
"""

from typing import cast

from pydantic import BaseModel
from pydantic_ai import RunContext

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.standalone._graph_helpers import step_ok_response
from veupath_chatbot.ai.tools.standalone._record_type_helpers import (
    find_record_type_for_search,
    find_record_type_hint,
)
from veupath_chatbot.ai.tools.standalone._validation_helpers import (
    StepOkResponse,
    get_graph,
    graph_not_found,
    validation_error_payload,
)
from veupath_chatbot.domain.strategy.ops import CombineOp, parse_op
from veupath_chatbot.integrations.veupathdb.wdk_models import WdkParams
from veupath_chatbot.platform.tool_errors import ToolErrorPayload, tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks
from veupath_chatbot.services.strategies.step_creation import (
    ColocationStepSpec,
    StepSpec,
    create_colocation_step,
    create_step,
)


class ColocationSpec(BaseModel):
    """Span logic parameters for genomic co-location.

    All fields are optional with sensible defaults.  region_a/region_b
    control which genomic region to compare: 'exact' uses the feature
    as-is; 'upstream'/'downstream' extend from the feature boundary;
    'custom' lets you set begin/end anchors, directions, and bp offsets.
    """

    operation: str = "overlaps"
    strand: str = "either strand"
    output: str = "a"
    region_a: str = "custom"
    begin_a: str = "start"
    begin_direction_a: str = "-"
    begin_offset_a: int = 1000
    end_a: str = "stop"
    end_direction_a: str = "+"
    end_offset_a: int = 0
    region_b: str = "exact"
    begin_b: str = "start"
    begin_direction_b: str = "+"
    begin_offset_b: int = 0
    end_b: str = "stop"
    end_direction_b: str = "+"
    end_offset_b: int = 0


def _make_callbacks(site_id: str) -> ValidationCallbacks:
    """Build validation callbacks bound to the given site."""

    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = True,
    ) -> str | None:
        return await find_record_type_for_search(
            site_id,
            record_type,
            search_name,
            require_match=require_match,
            allow_fallback=allow_fallback,
        )

    async def _hint(search_name: str, exclude: str | None = None) -> str | None:
        return await find_record_type_hint(site_id, search_name, exclude)

    return ValidationCallbacks(
        resolve_record_type_for_search=_resolve,
        find_record_type_hint=_hint,
        validation_error_payload=validation_error_payload,
    )


async def create_leaf_step(
    ctx: RunContext[AgentDeps],
    search_name: str,
    parameters: WdkParams,
    display_name: str = "",
    record_type: str | None = None,
    *,
    graph_id: str | None = None,
) -> StepOkResponse | ToolErrorPayload:
    """Create a new search step (leaf node) in the strategy graph.

    The search MUST have been discovered via ``get_search_overview`` first.
    This ensures the model has seen the parameter schema before filling values.

    Args:
        search_name: WDK search urlSegment (e.g. 'GenesByTaxon'). Must be discovered first.
        parameters: Parameter values for the search (paramName -> value string).
        display_name: Human-readable label for the step shown in the UI.
        record_type: Record type (e.g. 'transcript'). Auto-resolved if omitted.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    if not deps.agent_state.is_search_discovered(search_name):
        return tool_error(
            "DISCOVERY_REQUIRED",
            f"Call get_search_overview('{search_name}') first to see the parameter schema before creating a step.",
            required_action=f"get_search_overview(search_name='{search_name}')",
        )

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)

    callbacks = _make_callbacks(deps.site_id)

    spec = StepSpec(
        search_name=search_name,
        parameters=dict(parameters),
        record_type=record_type,
        display_name=display_name,
        _skip_auto_combine=True,
    )

    result = await create_step(
        graph=graph,
        site_id=session.site_id,
        spec=spec,
        callbacks=callbacks,
    )

    if result.error is not None or result.step is None:
        return (
            result.error
            if isinstance(result.error, ToolErrorPayload)
            else graph_not_found(graph_id)
        )

    return step_ok_response(session, graph, result.step)


async def combine_steps(
    ctx: RunContext[AgentDeps],
    step_a_id: str,
    step_b_id: str,
    operator: str,
    display_name: str | None = None,
    colocation_params: ColocationSpec | None = None,
    *,
    graph_id: str | None = None,
) -> StepOkResponse | ToolErrorPayload:
    """Combine two existing steps using a set operator.

    For boolean operators (INTERSECT, UNION, MINUS, RMINUS), creates a
    combine step joining step_a and step_b.

    For COLOCATE, creates a genomic co-location step finding genes from
    step_a that overlap or are near features from step_b on the same
    chromosome.

    Args:
        step_a_id: ID of the first step (primary input).
        step_b_id: ID of the second step (secondary input).
        operator: Set operation: INTERSECT, UNION, MINUS, RMINUS, or COLOCATE.
        display_name: Human-readable label for the combined step.
        colocation_params: Span logic parameters (only for COLOCATE operator).
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)

    # Validate both step IDs exist in the graph.
    if step_a_id not in graph.steps:
        return tool_error(
            "STEP_NOT_FOUND",
            f"Step A not found: {step_a_id}",
            stepId=step_a_id,
        )
    if step_b_id not in graph.steps:
        return tool_error(
            "STEP_NOT_FOUND",
            f"Step B not found: {step_b_id}",
            stepId=step_b_id,
        )

    # Parse and validate operator.
    try:
        parsed_op = parse_op(operator)
    except ValueError:
        return tool_error(
            "VALIDATION_ERROR",
            f"Invalid operator: {operator}. Use INTERSECT, UNION, MINUS, RMINUS, or COLOCATE.",
        )

    callbacks = _make_callbacks(deps.site_id)

    if parsed_op == CombineOp.COLOCATE:
        span_params = (colocation_params or ColocationSpec()).model_dump()
        result = await create_colocation_step(
            graph=graph,
            site_id=session.site_id,
            spec=ColocationStepSpec(
                primary_step_id=step_a_id,
                secondary_step_id=step_b_id,
                colocation_kwargs=span_params,
                display_name=display_name,
            ),
            callbacks=callbacks,
        )
    else:
        spec = StepSpec(
            primary_input_step_id=step_a_id,
            secondary_input_step_id=step_b_id,
            operator=parsed_op.value,
            display_name=display_name,
        )
        result = await create_step(
            graph=graph,
            site_id=session.site_id,
            spec=spec,
            callbacks=callbacks,
        )

    if result.error is not None or result.step is None:
        return (
            result.error
            if isinstance(result.error, ToolErrorPayload)
            else graph_not_found(graph_id)
        )

    return step_ok_response(session, graph, result.step)


async def transform_step(
    ctx: RunContext[AgentDeps],
    input_step_id: str,
    transform_name: str,
    parameters: WdkParams | None = None,
    display_name: str | None = None,
    *,
    graph_id: str | None = None,
) -> StepOkResponse | ToolErrorPayload:
    """Create a transform step that takes an existing step as input.

    When custom parameters are provided, the transform search must have
    been discovered via ``get_search_overview`` first (discovery gate).
    When parameters is None the transform proceeds with defaults and no
    discovery is needed.

    Args:
        input_step_id: ID of the step whose results feed into this transform.
        transform_name: WDK transform search urlSegment (e.g. 'GenesByOrthologs').
        parameters: Parameter values for the transform. If None, uses defaults.
        display_name: Human-readable label for the transform step.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    # Only enforce gate when custom parameters are provided
    if parameters and not deps.agent_state.is_search_discovered(transform_name):
        return tool_error(
            "DISCOVERY_REQUIRED",
            f"Call get_search_overview('{transform_name}') first to see the parameter schema.",
            required_action=f"get_search_overview(search_name='{transform_name}')",
        )

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)

    # Verify input step exists in the graph.
    if input_step_id not in graph.steps:
        return tool_error(
            "STEP_NOT_FOUND",
            f"Input step '{input_step_id}' not found in graph.",
            graphId=graph.id,
        )

    callbacks = _make_callbacks(deps.site_id)

    spec = StepSpec(
        search_name=transform_name,
        parameters=cast("JSONObject | None", parameters),
        primary_input_step_id=input_step_id,
        display_name=display_name,
    )

    result = await create_step(
        graph=graph,
        site_id=session.site_id,
        spec=spec,
        callbacks=callbacks,
    )

    if result.error is not None or result.step is None:
        return (
            result.error
            if isinstance(result.error, ToolErrorPayload)
            else graph_not_found(graph_id)
        )

    return step_ok_response(session, graph, result.step)
