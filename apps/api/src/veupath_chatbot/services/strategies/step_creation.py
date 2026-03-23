"""Step creation business logic.

Extracts the validation-heavy step creation workflow from the AI tool layer
so it can be tested and reused independently. All I/O dependencies (WDK
client, discovery service) are injected via callbacks or explicit parameters.
"""

from dataclasses import dataclass

from veupath_chatbot.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from veupath_chatbot.domain.strategy.ops import ColocationParams
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks
from veupath_chatbot.services.strategies.step_validation import (
    _resolve_record_type_for_step,
    _resolve_search_name_and_validate,
    _StepInputs,
    _validate_inputs_and_roots,
)
from veupath_chatbot.services.strategies.step_wdk_push import _push_step_to_wdk

logger = get_logger(__name__)

COMBINE_PLACEHOLDER_SEARCH_NAME = COMBINE_SEARCH_NAME


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
    upstream: int | None = None
    downstream: int | None = None
    strand: str | None = None


@dataclass
class StepCreationResult:
    """Result of step creation: either a successfully added step or an error payload."""

    step: PlanStepNode | None
    step_id: str | None
    error: JSONObject | None
    wdk_step_id: int | None = None
    wdk_validation: WDKValidation | None = None


def _error_result(error: JSONObject) -> StepCreationResult:
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

    if (
        not primary_input_step_id
        and not secondary_input_step_id
        and not operator
    ):
        left, right, op = coerce_wdk_boolean_question_params(
            parameters=parameters
        )
        if left and right and op:
            return left, right, op

    return primary_input_step_id, secondary_input_step_id, operator


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
    primary_input, secondary_input, error = _validate_inputs_and_roots(
        graph,
        primary_input_step_id,
        secondary_input_step_id,
        operator,
    )
    if error is not None:
        return _error_result(error)

    # Resolve record type context for the graph.
    graph.record_type = await _resolve_record_type_for_step(
        graph.record_type,
        spec.record_type,
        spec.search_name,
        callbacks.resolve_record_type_for_search,
    )

    search_name, parsed_op, step_error = (
        await _resolve_search_name_and_validate(
            graph=graph,
            site_id=site_id,
            spec_search_name=spec.search_name,
            inputs=_StepInputs(
                primary=primary_input,
                secondary=secondary_input,
                operator=operator,
                params=parameters,
            ),
            callbacks=callbacks,
            combine_placeholder=COMBINE_PLACEHOLDER_SEARCH_NAME,
        )
    )
    if step_error is not None:
        return _error_result(step_error)

    colocation = ColocationParams.from_raw(
        parsed_op, spec.upstream, spec.downstream, spec.strand
    )

    # Build and add the step.
    step = PlanStepNode(
        search_name=search_name,
        parameters=parameters,
        primary_input=primary_input,
        secondary_input=secondary_input,
        operator=parsed_op,
        colocation_params=colocation,
        display_name=spec.display_name or search_name,
    )

    step_id = graph.add_step(step)

    logger.info("Created step", step_id=step_id, search=search_name)

    # Push step to WDK immediately (best-effort).
    wdk_step_id, wdk_validation = await _push_step_to_wdk(
        graph=graph,
        step=step,
        site_id=site_id,
        search_name=search_name,
        parameters=parameters,
        parsed_op=parsed_op,
    )

    return StepCreationResult(
        step=step,
        step_id=step_id,
        error=None,
        wdk_step_id=wdk_step_id,
        wdk_validation=wdk_validation,
    )
