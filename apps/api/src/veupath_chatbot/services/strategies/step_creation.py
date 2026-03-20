"""Step creation business logic.

Extracts the validation-heavy step creation workflow from the AI tool layer
so it can be tested and reused independently. All I/O dependencies (WDK
client, discovery service) are injected via callbacks or explicit parameters.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    find_input_step_param,
    unwrap_search_data,
)
from veupath_chatbot.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp, parse_op
from veupath_chatbot.domain.strategy.organism import extract_output_organisms
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.catalog.param_validation import validate_parameters

logger = get_logger(__name__)

COMBINE_PLACEHOLDER_SEARCH_NAME = COMBINE_SEARCH_NAME

# Callback type aliases for injected dependencies.
ResolveRecordTypeFn = Callable[
    [str | None, str | None, bool, bool], Awaitable[str | None]
]
FindRecordTypeHintFn = Callable[[str, str | None], Awaitable[str | None]]
ExtractVocabOptionsFn = Callable[[JSONObject], list[str]]


@dataclass
class StepCreationResult:
    """Result of step creation: either a successfully added step or an error payload."""

    step: PlanStepNode | None
    step_id: str | None
    error: JSONObject | None


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

    # operator can be provided as bq_operator; strip it from params in favor of structural operator
    if "bq_operator" in parameters:
        raw = parameters.pop("bq_operator", None)
        if raw is not None:
            op = str(raw)

    if left_id and right_id and op:
        return left_id, right_id, op
    return None, None, None


def _validate_inputs(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[PlanStepNode | None, PlanStepNode | None, JSONObject | None]:
    """Validate and resolve input step references.

    :returns: (primary_input, secondary_input, error_or_none).
        If error is not None, the caller should return it immediately.
    """
    primary_input = None
    secondary_input = None

    if primary_input_step_id:
        primary_input = graph.get_step(primary_input_step_id)
        if not primary_input:
            return (
                None,
                None,
                tool_error(
                    ErrorCode.STEP_NOT_FOUND,
                    "Primary input step not found.",
                    graphId=graph.id,
                    stepId=primary_input_step_id,
                ),
            )
    if secondary_input_step_id:
        secondary_input = graph.get_step(secondary_input_step_id)
        if not secondary_input:
            return (
                None,
                None,
                tool_error(
                    ErrorCode.STEP_NOT_FOUND,
                    "Secondary input step not found.",
                    graphId=graph.id,
                    stepId=secondary_input_step_id,
                ),
            )
        if primary_input is None:
            return (
                None,
                None,
                tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "secondary_input_step_id requires primary_input_step_id.",
                    graphId=graph.id,
                ),
            )
        if not operator:
            return (
                None,
                None,
                tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "operator is required when secondary_input_step_id is provided.",
                    graphId=graph.id,
                ),
            )

    return primary_input, secondary_input, None


def _validate_root_status(
    graph: StrategyGraph,
    step_id: str,
) -> JSONObject | None:
    """Check that *step_id* is a subtree root. Return an error payload if not."""
    if step_id in graph.roots:
        return None
    consumer = graph.find_consumer(step_id)
    return tool_error(
        ErrorCode.INVALID_STRATEGY,
        f"Step '{step_id}' is not a subtree root — it is already consumed by step '{consumer}'. "
        "Only current subtree roots can be used as inputs.",
        graphId=graph.id,
        stepId=step_id,
        consumedBy=consumer,
        availableRoots=cast("JSONValue", sorted(graph.roots)),
    )


async def _resolve_and_set_record_type(
    graph: StrategyGraph,
    record_type: str | None,
    search_name: str | None,
    resolve_record_type_for_search: ResolveRecordTypeFn,
) -> str:
    """Establish best-effort record type context on the graph. Returns the resolved type."""
    resolved = graph.record_type or record_type
    if resolved is None and search_name:
        resolved = await resolve_record_type_for_search(
            None, search_name, require_match=False, allow_fallback=True
        )
    if resolved is None:
        resolved = "gene"
    graph.record_type = resolved
    return resolved


# ---------------------------------------------------------------------------
# Search resolution + parameter validation
# ---------------------------------------------------------------------------


async def _resolve_search_and_validate_params(
    *,
    graph: StrategyGraph,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    parameters: JSONObject,
    resolve_record_type_for_search: ResolveRecordTypeFn,
    find_record_type_hint: FindRecordTypeHintFn,
    extract_vocab_options: ExtractVocabOptionsFn,
    validation_error_payload: Callable[[ValidationError], JSONObject],
) -> tuple[str, JSONObject | None]:
    """Resolve record type for a search and validate its parameters.

    Shared by leaf and transform validation paths.

    :returns: (resolved_record_type, error_or_none).
    """
    rt = await resolve_record_type_for_search(
        resolved_record_type, search_name, require_match=True, allow_fallback=True
    )
    if rt is None:
        record_type_hint = await find_record_type_hint(
            search_name, resolved_record_type
        )
        return resolved_record_type, tool_error(
            ErrorCode.SEARCH_NOT_FOUND,
            f"Unknown or invalid search: {search_name}",
            recordType=resolved_record_type,
            recordTypeHint=record_type_hint,
        )
    graph.record_type = rt

    try:
        await validate_parameters(
            site_id=site_id,
            record_type=rt,
            search_name=search_name,
            parameters=parameters,
            resolve_record_type_for_search=resolve_record_type_for_search,
            find_record_type_hint=find_record_type_hint,
            extract_vocab_options=extract_vocab_options,
        )
    except ValidationError as exc:
        return rt, validation_error_payload(exc)

    return rt, None


async def _validate_leaf_or_transform(
    *,
    graph: StrategyGraph,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    parameters: JSONObject,
    is_transform: bool,
    resolve_record_type_for_search: ResolveRecordTypeFn,
    find_record_type_hint: FindRecordTypeHintFn,
    extract_vocab_options: ExtractVocabOptionsFn,
    validation_error_payload: Callable[[ValidationError], JSONObject],
) -> JSONObject | None:
    """Validate a leaf or transform step. Returns error payload or None on success.

    Shared validation (search resolution + parameter validation) runs first,
    then kind-specific checks:
    - Leaf: fold-change duplicate sample guard.
    - Transform: confirm the search accepts an input step.
    """
    rt, error = await _resolve_search_and_validate_params(
        graph=graph,
        site_id=site_id,
        resolved_record_type=resolved_record_type,
        search_name=search_name,
        parameters=parameters,
        resolve_record_type_for_search=resolve_record_type_for_search,
        find_record_type_hint=find_record_type_hint,
        extract_vocab_options=extract_vocab_options,
        validation_error_payload=validation_error_payload,
    )
    if error is not None:
        return error

    if is_transform:
        return await _validate_transform_input_param(rt, site_id, search_name)

    # Leaf-specific: fold-change searches with identical ref and comp samples
    # produce meaningless results.
    return _validate_fold_change_samples(search_name, parameters)


def _validate_fold_change_samples(
    search_name: str,
    parameters: JSONObject,
) -> JSONObject | None:
    """Guard against identical ref/comp samples in fold-change searches."""
    ref = parameters.get("samples_fc_ref_generic") or parameters.get(
        "samples_percentile_generic"
    )
    comp = parameters.get("samples_fc_comp_generic")
    if ref and comp and str(ref) == str(comp):
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Reference and comparison samples are identical — this will produce "
            "meaningless fold-change results. Set different samples for reference "
            "vs comparison.",
            searchName=search_name,
            ref=ref,
            comp=comp,
        )
    return None


async def _validate_transform_input_param(
    rt: str,
    site_id: str,
    search_name: str,
) -> JSONObject | None:
    """Confirm the search accepts an input step (required for transforms)."""
    try:
        wdk = get_wdk_client(site_id)
        details = await wdk.get_search_details(rt, search_name, expand_params=True)
    except Exception as exc:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Failed to load search metadata for transform validation.",
            recordType=rt,
            searchName=search_name,
            detail=str(exc),
        )
    specs = adapt_param_specs(unwrap_search_data(details) or {})
    input_param = find_input_step_param(specs)
    if not input_param:
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            f"Search '{search_name}' cannot be used as a transform: it does not accept an input step. "
            f"Call list_transforms(record_type='{rt}') to see available transforms (e.g. GenesByOrthologs for ortholog conversion).",
            recordType=rt,
            searchName=search_name,
            suggestedFix={
                "message": "Call list_transforms() to find the correct transform search, or create this as a leaf step and combine with INTERSECT/UNION/MINUS.",
                "asLeaf": {"searchName": search_name, "recordType": rt},
            },
        )
    return None


def _validate_cross_organism_intersect(
    graph: StrategyGraph,
    primary_input: PlanStepNode,
    secondary_input: PlanStepNode,
) -> JSONObject | None:
    """Guard: INTERSECT between different organisms always returns 0."""
    primary_orgs = extract_output_organisms(primary_input)
    secondary_orgs = extract_output_organisms(secondary_input)
    if (
        primary_orgs is not None
        and secondary_orgs is not None
        and primary_orgs.isdisjoint(secondary_orgs)
    ):
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            f"Cannot INTERSECT steps with different organism scopes "
            f"({', '.join(sorted(primary_orgs))} vs {', '.join(sorted(secondary_orgs))}). "
            f"Gene IDs from different species never match, so this always returns 0 results. "
            f"Apply organism-specific filters BEFORE any ortholog transform, not after.",
            graphId=graph.id,
            primaryOrganisms=cast("JSONValue", sorted(primary_orgs)),
            secondaryOrganisms=cast("JSONValue", sorted(secondary_orgs)),
        )
    return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def create_step(
    *,
    graph: StrategyGraph,
    site_id: str,
    search_name: str | None = None,
    parameters: JSONObject | None = None,
    record_type: str | None = None,
    primary_input_step_id: str | None = None,
    secondary_input_step_id: str | None = None,
    operator: str | None = None,
    display_name: str | None = None,
    upstream: int | None = None,
    downstream: int | None = None,
    strand: str | None = None,
    resolve_record_type_for_search: ResolveRecordTypeFn,
    find_record_type_hint: FindRecordTypeHintFn,
    extract_vocab_options: ExtractVocabOptionsFn,
    validation_error_payload: Callable[[ValidationError], JSONObject],
) -> StepCreationResult:
    """Create a new strategy step with full validation.

    Step kind is inferred from structure:
    - leaf step: no inputs
    - unary/transform step: primary_input_step_id only
    - binary/combine step: primary_input_step_id + secondary_input_step_id (+ operator)

    :returns: StepCreationResult with either step/step_id or error.
    """
    parameters = parameters or {}

    # WDK compatibility: if caller encoded a boolean combine as WDK boolean-question
    # parameters, translate it into structural inputs.
    if not primary_input_step_id and not secondary_input_step_id and not operator:
        left, right, op = coerce_wdk_boolean_question_params(parameters=parameters)
        if left and right and op:
            primary_input_step_id = left
            secondary_input_step_id = right
            operator = op

    # Validate and resolve input steps.
    primary_input, secondary_input, error = _validate_inputs(
        graph, primary_input_step_id, secondary_input_step_id, operator
    )
    if error is not None:
        return _error_result(error)

    # Validate root status for input steps.
    for step_node, step_id in (
        (primary_input, primary_input_step_id),
        (secondary_input, secondary_input_step_id),
    ):
        if step_node is not None and step_id is not None and step_id not in graph.roots:
            root_error = _validate_root_status(graph, step_id)
            if root_error is not None:
                return _error_result(root_error)

    # Resolve record type.
    resolved_record_type = await _resolve_and_set_record_type(
        graph, record_type, search_name, resolve_record_type_for_search
    )

    # Determine search_name requirement.
    is_binary = primary_input is not None and secondary_input is not None
    if not search_name:
        if is_binary:
            search_name = COMBINE_PLACEHOLDER_SEARCH_NAME
        else:
            return _error_result(
                tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "search_name is required for leaf and transform steps.",
                    graphId=graph.id,
                )
            )

    # Validate leaf and transform steps (binary steps skip this).
    if not is_binary:
        step_error = await _validate_leaf_or_transform(
            graph=graph,
            site_id=site_id,
            resolved_record_type=resolved_record_type,
            search_name=search_name,
            parameters=parameters,
            is_transform=primary_input is not None,
            resolve_record_type_for_search=resolve_record_type_for_search,
            find_record_type_hint=find_record_type_hint,
            extract_vocab_options=extract_vocab_options,
            validation_error_payload=validation_error_payload,
        )
        if step_error is not None:
            return _error_result(step_error)

    # Parse operator and build colocation params.
    parsed_op = parse_op(operator) if secondary_input is not None and operator else None
    colocation = ColocationParams.from_raw(parsed_op, upstream, downstream, strand)

    # Cross-organism combine guard.
    if (
        parsed_op == CombineOp.INTERSECT
        and primary_input is not None
        and secondary_input is not None
    ):
        organism_error = _validate_cross_organism_intersect(
            graph, primary_input, secondary_input
        )
        if organism_error is not None:
            return _error_result(organism_error)

    # Build and add the step.
    step = PlanStepNode(
        search_name=search_name,
        parameters=parameters,
        primary_input=primary_input,
        secondary_input=secondary_input,
        operator=parsed_op,
        colocation_params=colocation,
        display_name=display_name or search_name,
    )

    step_id = graph.add_step(step)

    logger.info("Created step", step_id=step_id, search=search_name)
    return StepCreationResult(step=step, step_id=step_id, error=None)
