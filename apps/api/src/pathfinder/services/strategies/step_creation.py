"""Step creation business logic.

Extracts the validation-heavy step creation workflow from the AI tool layer
so it can be tested and reused independently. All I/O dependencies (WDK
client, discovery service) are injected via callbacks or explicit parameters.
"""

from dataclasses import dataclass

from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp, parse_op
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.integrations.veupathdb.wdk_models import WDKValidation
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_validation import ValidationCallbacks
from pathfinder.services.strategies.input_resolution import (
    StepInputs,
    validate_inputs_and_roots,
)
from pathfinder.services.strategies.kind_validation import (
    resolve_search_name_and_validate,
)
from pathfinder.services.strategies.search_resolution import (
    resolve_record_type_for_step,
)
from pathfinder.services.strategies.step_wdk_push import _push_step_to_wdk

logger = get_logger(__name__)

COMBINE_PLACEHOLDER_SEARCH_NAME = COMBINE_SEARCH_NAME


@dataclass
class InlineSpec:
    """Inline step specification for atomic subtree construction.

    Used when the AI model needs to create intermediate steps (e.g. two
    transforms on different inputs) as part of a single ``create_step``
    call.  The created step is immediately consumed as input to the outer
    step, so it should NOT auto-combine with the current root.
    """

    search_name: str
    parameters: JSONObject | None = None
    display_name: str | None = None
    primary_input_step_id: str | None = None


@dataclass
class StepSpec:
    """Specification for creating a strategy step.

    Bundles all step-specific inputs to keep :func:`create_step` under the
    six-argument limit while preserving a clear call-site interface.
    """

    search_name: str | None = None
    parameters: JSONObject | None = None
    record_type: str | None = None
    primary_input_step_id: str | None = None
    secondary_input_step_id: str | None = None
    operator: str | None = None
    display_name: str | None = None
    colocation_params: ColocationParams | None = None
    combine_with_step_id: str | None = None
    combine_operator: str | None = None  # defaults to "INTERSECT" if not provided
    _skip_auto_combine: bool = False


@dataclass
class StepCreationResult:
    """Result of step creation: either a successfully added step or an error payload."""

    step: PlanStepNode | None
    step_id: str | None
    error: ToolErrorPayload | None
    wdk_step_id: int | None = None
    wdk_validation: WDKValidation | None = None
    wdk_push_error: str | None = None
    combine_step: PlanStepNode | None = None
    combine_step_id: str | None = None
    combine_wdk_step_id: int | None = None
    combine_wdk_push_error: str | None = None


def _error_result(error: ToolErrorPayload) -> StepCreationResult:
    """Shorthand for an error-only StepCreationResult."""
    return StepCreationResult(step=None, step_id=None, error=error)


def coerce_wdk_boolean_question_params(
    *,
    parameters: JSONObject,
) -> tuple[str | None, str | None, str | None]:
    """Extract left/right/operator from WDK boolean-question parameter conventions.

    WDK boolean questions sometimes encode combines as a "boolean_question_*"
    search with ``bq_left_op_``, ``bq_right_op_``, ``bq_operator``. Our graph
    model represents combines structurally; we translate these WDK boolean
    keys from the parameters dict.

    Mutates *parameters* by removing any ``bq_*`` keys it consumes.

    :param parameters: WDK boolean-question parameters (may contain
        ``bq_left_op_``, ``bq_right_op_``, ``bq_operator``).
    :returns: Tuple of (left_step_id, right_step_id, operator) or (None, None, None).
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

    # operator can be provided as bq_operator; strip it from params
    # in favor of structural operator
    if "bq_operator" in parameters:
        raw = parameters.pop("bq_operator", None)
        if raw is not None:
            op = str(raw)

    if left_id and right_id and op:
        return left_id, right_id, op
    return None, None, None


def _resolve_inputs_from_spec(
    spec: StepSpec,
    parameters: JSONObject,
) -> tuple[str | None, str | None, str | None]:
    """Return (primary_input_step_id, secondary_input_step_id, operator).

    Applies WDK boolean-question param coercion when no structural inputs
    were given.
    """
    primary_input_step_id = spec.primary_input_step_id
    secondary_input_step_id = spec.secondary_input_step_id
    operator = spec.operator

    if not primary_input_step_id and not secondary_input_step_id and not operator:
        left, right, op = coerce_wdk_boolean_question_params(parameters=parameters)
        if left and right and op:
            return left, right, op

    return primary_input_step_id, secondary_input_step_id, operator


def _add_step_to_graph(
    *,
    graph: StrategyGraph,
    step: PlanStepNode,
    search_name: str,
    spec: StepSpec,
    needs_combine: bool,
    combine_with_step_id: str | None,
) -> tuple[str | None, PlanStepNode | None, str | None]:
    """Insert *step* into the graph, returning (step_id, combine_step, combine_id).

    Returns ``(None, None, None)`` when *combine_with_step_id* is set but
    missing from the graph (caller should return an error).

    Handles three modes:
    - **combine**: wraps *step* + an existing step into a combine node.
    - **inline** (``_skip_auto_combine``): registers in ``graph.steps``
      without touching roots — the caller consumes this step immediately.
    - **direct**: first step or explicit binary/transform via ``add_step``.
    """
    if needs_combine and combine_with_step_id is not None:
        combine_op = (
            parse_op(spec.combine_operator)
            if spec.combine_operator
            else CombineOp.INTERSECT
        )
        if combine_with_step_id not in graph.steps:
            return None, None, None

        _new_step_id, combine_id = graph.insert_step_with_combine(
            step, combine_with_step_id, combine_op,
        )
        combine_step = graph.steps[combine_id]
        logger.info(
            "Created step with combine",
            step_id=step.id,
            combine_id=combine_id,
            search=search_name,
            operator=str(combine_op),
        )
        return step.id, combine_step, combine_id

    # add_step registers the step in graph.steps AND graph.roots.
    # The _skip_auto_combine flag only disables the combine-with-existing
    # logic above — the step still needs root tracking for auto-build.
    graph.add_step(step)
    logger.info("Created step", step_id=step.id, search=search_name, skip_auto_combine=spec._skip_auto_combine)
    return step.id, None, None


async def create_step(
    *,
    graph: StrategyGraph,
    site_id: str,
    spec: StepSpec,
    callbacks: ValidationCallbacks,
) -> StepCreationResult:
    """Create a new strategy step with full validation.

    Step kind is inferred from structure:
    - leaf step: no inputs
    - unary/transform step: primary_input_step_id only
    - binary/combine step: primary_input_step_id + secondary_input_step_id (+ operator)

    :returns: StepCreationResult with either step/step_id or error.
    """
    parameters: JSONObject = spec.parameters or {}
    primary_input_step_id, secondary_input_step_id, operator = (
        _resolve_inputs_from_spec(spec, parameters)
    )

    # Validate and resolve input steps (including root-status check).
    primary_input, secondary_input, error = validate_inputs_and_roots(
        graph,
        primary_input_step_id,
        secondary_input_step_id,
        operator,
    )
    if error is not None:
        return _error_result(error)

    # Resolve record type context for the graph.
    graph.record_type = await resolve_record_type_for_step(
        graph.record_type,
        spec.record_type,
        spec.search_name,
        callbacks.resolve_record_type_for_search,
    )

    search_name, parsed_op, step_error = await resolve_search_name_and_validate(
        graph=graph,
        site_id=site_id,
        spec_search_name=spec.search_name,
        inputs=StepInputs(
            primary=primary_input,
            secondary=secondary_input,
            operator=operator,
            params=parameters,
        ),
        callbacks=callbacks,
        combine_placeholder=COMBINE_PLACEHOLDER_SEARCH_NAME,
    )
    if step_error is not None:
        return _error_result(step_error)

    # Build the step node.
    step = PlanStepNode(
        search_name=search_name,
        parameters=parameters,
        primary_input=primary_input,
        secondary_input=secondary_input,
        operator=parsed_op,
        colocation_params=spec.colocation_params,
        display_name=spec.display_name or search_name,
    )

    # Determine whether we need a combine node.
    combine_with_step_id = spec.combine_with_step_id
    needs_combine = False

    if (
        graph.steps
        and combine_with_step_id is None
        and not primary_input
        and not secondary_input
        and not spec._skip_auto_combine
    ):
        # Auto-combine with current root when graph already has steps
        # and this is a leaf step (not an explicit binary/transform).
        combine_with_step_id = next(iter(graph.roots))
        needs_combine = True
    elif combine_with_step_id is not None:
        needs_combine = True

    step_id, combine_step, combine_id = _add_step_to_graph(
        graph=graph,
        step=step,
        search_name=search_name,
        spec=spec,
        needs_combine=needs_combine,
        combine_with_step_id=combine_with_step_id,
    )
    if step_id is None:
        return _error_result(tool_error(
            "STEP_NOT_FOUND",
            f"combine_with_step_id '{combine_with_step_id}' not found in graph.",
        ))

    # Push leaf step to WDK immediately (best-effort).
    wdk_step_id, wdk_validation, push_error = await _push_step_to_wdk(
        graph=graph,
        step=step,
        site_id=site_id,
        search_name=search_name,
        parameters=parameters,
        parsed_op=parsed_op,
    )

    if push_error:
        graph.wdk_push_errors[step.id] = push_error

    # Push combine step to WDK if one was created.
    combine_wdk_step_id: int | None = None
    combine_wdk_push_error: str | None = None
    if combine_step is not None:
        combine_wdk_step_id, _, combine_wdk_push_error = await _push_step_to_wdk(
            graph=graph,
            step=combine_step,
            site_id=site_id,
            search_name=COMBINE_SEARCH_NAME,
            parameters={},
            parsed_op=combine_step.operator,
        )
        if combine_wdk_push_error:
            graph.wdk_push_errors[combine_step.id] = combine_wdk_push_error

    return StepCreationResult(
        step=step,
        step_id=step_id,
        error=None,
        wdk_step_id=wdk_step_id,
        wdk_validation=wdk_validation,
        wdk_push_error=push_error,
        combine_step=combine_step,
        combine_step_id=combine_id,
        combine_wdk_step_id=combine_wdk_step_id,
        combine_wdk_push_error=combine_wdk_push_error,
    )


async def resolve_inline_step(
    *,
    graph: StrategyGraph,
    site_id: str,
    spec: InlineSpec,
    callbacks: ValidationCallbacks,
) -> StepCreationResult:
    """Create a step from an inline spec without auto-combine.

    Used for atomic subtree construction — the created step is immediately
    consumed as input to an outer step, so it should NOT auto-combine with
    the current root and should NOT be added to ``graph.roots``.
    """
    step_spec = StepSpec(
        search_name=spec.search_name,
        parameters=spec.parameters,
        display_name=spec.display_name,
        primary_input_step_id=spec.primary_input_step_id,
        _skip_auto_combine=True,
    )
    return await create_step(
        graph=graph,
        site_id=site_id,
        spec=step_spec,
        callbacks=callbacks,
    )


@dataclass
class ColocationStepSpec:
    """Input spec for creating a COLOCATE step."""

    primary_step_id: str
    secondary_step_id: str
    colocation_kwargs: JSONObject
    display_name: str | None = None


async def create_colocation_step(
    *,
    graph: StrategyGraph,
    site_id: str,
    spec: ColocationStepSpec,
    callbacks: ValidationCallbacks,
) -> StepCreationResult:
    """Create a COLOCATE step via GenesBySpanLogic.

    Constructs ``ColocationParams`` from raw kwargs (model-provided),
    wraps into a ``StepSpec``, and delegates to :func:`create_step`.

    Preserves the graph's record type because the secondary input (Set B)
    may be a different record type (e.g. ``genomic-segment`` for DNA motifs)
    that should not contaminate the strategy's record type.
    """
    saved_record_type = graph.record_type
    colocation = ColocationParams.model_validate(spec.colocation_kwargs)
    step_spec = StepSpec(
        primary_input_step_id=spec.primary_step_id,
        secondary_input_step_id=spec.secondary_step_id,
        operator="COLOCATE",
        display_name=spec.display_name,
        colocation_params=colocation,
    )
    result = await create_step(graph=graph, site_id=site_id, spec=step_spec, callbacks=callbacks)
    # Restore record type — GenesBySpanLogic lives under transcript,
    # not whatever the secondary input's record type is.
    graph.record_type = saved_record_type or "transcript"
    return result
