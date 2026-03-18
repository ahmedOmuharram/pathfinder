"""Step creation business logic.

Extracts the validation-heavy step creation workflow from the AI tool layer
so it can be tested and reused independently. All I/O dependencies (WDK
client, discovery service) are injected via callbacks or explicit parameters.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, cast

from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    find_input_step_param,
    unwrap_search_data,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp, parse_op
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.catalog.param_validation import validate_parameters

logger = get_logger(__name__)

COMBINE_PLACEHOLDER_SEARCH_NAME = "__combine__"

# Callback type aliases for injected dependencies.
ResolveRecordTypeFn = Callable[
    [str | None, str | None, bool, bool], Awaitable[str | None]
]
FindRecordTypeHintFn = Callable[[str, str | None], Awaitable[str | None]]
ExtractVocabOptionsFn = Callable[[JSONObject], list[str]]


async def _auto_expand_organism_param(
    site_id: str,
    record_type: str,
    parameters: JSONObject,
) -> JSONObject:
    """Auto-expand organism for GenesByOrthologPattern.

    The search requires ALL leaf organisms to be selected to return results.
    The model typically passes only one or a few. This fetches the organism
    vocabulary tree and populates all leaf values automatically.
    """
    import json as _json

    from veupath_chatbot.domain.parameters.vocab_utils import collect_leaf_terms

    org_raw = parameters.get("organism")
    current: list[str] = []
    if isinstance(org_raw, str):
        try:
            parsed = _json.loads(org_raw)
            if isinstance(parsed, list):
                current = [str(v) for v in parsed]
        except _json.JSONDecodeError:
            current = [org_raw] if org_raw else []
    elif isinstance(org_raw, list):
        current = [str(v) for v in org_raw]

    if len(current) > 5:
        return parameters

    try:
        from veupath_chatbot.integrations.veupathdb.discovery import (
            get_discovery_service,
        )

        discovery = get_discovery_service()
        details = await discovery.get_search_details(
            site_id, record_type, "GenesByOrthologPattern", expand_params=True
        )
        if not isinstance(details, dict):
            return parameters
        search_data = details.get("searchData", details)
        if not isinstance(search_data, dict):
            return parameters
        raw_params = search_data.get("parameters", [])
        if not isinstance(raw_params, list):
            return parameters
        for p in raw_params:
            if not isinstance(p, dict) or p.get("name") != "organism":
                continue
            vocab = p.get("vocabulary")
            if not isinstance(vocab, dict):
                break
            all_leaves = [t for t in collect_leaf_terms(vocab) if t != "@@fake@@"]
            if all_leaves:
                logger.info(
                    "Auto-expanded organism for GenesByOrthologPattern",
                    original_count=len(current),
                    expanded_count=len(all_leaves),
                )
                return {**parameters, "organism": _json.dumps(all_leaves)}
            break
    except Exception as exc:
        logger.warning("Failed to auto-expand organism param", error=str(exc))

    return parameters


@dataclass
class StepCreationResult:
    """Result of step creation: either a successfully added step or an error payload."""

    step: PlanStepNode | None
    step_id: str | None
    error: JSONObject | None


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


def _find_consumer(graph: StrategyGraph, step_id: str) -> str | None:
    """Find the step that already consumes *step_id* as an input."""
    return next(
        (
            s.id
            for s in graph.steps.values()
            if (
                getattr(getattr(s, "primary_input", None), "id", None) == step_id
                or getattr(getattr(s, "secondary_input", None), "id", None) == step_id
            )
        ),
        None,
    )


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
    label: str,
) -> JSONObject | None:
    """Check that *step_id* is a subtree root. Return an error payload if not."""
    if step_id in graph.roots:
        return None
    consumer = _find_consumer(graph, step_id)
    return tool_error(
        ErrorCode.INVALID_STRATEGY,
        f"Step '{step_id}' is not a subtree root — it is already consumed by step '{consumer}'. "
        "Only current subtree roots can be used as inputs.",
        graphId=graph.id,
        stepId=step_id,
        consumedBy=consumer,
        availableRoots=cast(JSONValue, sorted(graph.roots)),
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
        resolved = await resolve_record_type_for_search(None, search_name, False, True)
    if resolved is None:
        resolved = "gene"
    graph.record_type = resolved
    return resolved


async def _validate_leaf_step(
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
) -> JSONObject | None:
    """Validate a leaf step (no inputs). Returns error payload or None on success."""
    rt = await resolve_record_type_for_search(
        resolved_record_type, search_name, True, True
    )
    if rt is None:
        record_type_hint = await find_record_type_hint(
            search_name, resolved_record_type
        )
        return tool_error(
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
        return validation_error_payload(exc)

    # Guard: fold-change searches with identical ref and comp samples produce
    # meaningless results. Catch this early so the model can fix it.
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


async def _validate_transform_step(
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
) -> JSONObject | None:
    """Validate a transform step (primary input only). Returns error payload or None."""
    rt = await resolve_record_type_for_search(
        resolved_record_type, search_name, True, True
    )
    if rt is None:
        record_type_hint = await find_record_type_hint(
            search_name, resolved_record_type
        )
        return tool_error(
            ErrorCode.SEARCH_NOT_FOUND,
            f"Unknown or invalid search: {search_name}",
            recordType=resolved_record_type,
            recordTypeHint=record_type_hint,
        )
    graph.record_type = rt

    # Validate parameters against WDK specs.
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
        return validation_error_payload(exc)

    # Confirm the question supports an input step.
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


def _build_colocation_params(
    operator: CombineOp | None,
    upstream: int | None,
    downstream: int | None,
    strand: str | None,
) -> ColocationParams | None:
    """Build ColocationParams if the operator is COLOCATE."""
    if operator != CombineOp.COLOCATE:
        return None
    strand_value: Literal["same", "opposite", "both"]
    if strand in ("same", "opposite", "both"):
        strand_value = cast(Literal["same", "opposite", "both"], strand)
    else:
        strand_value = "both"
    return ColocationParams(
        upstream=upstream or 0,
        downstream=downstream or 0,
        strand=strand_value,
    )


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

    # Auto-expand organism for GenesByOrthologPattern: the search requires ALL
    # leaf organisms to be selected, but the model typically passes only one.
    # Fetch the full vocabulary tree and populate all leaves automatically.
    if search_name == "GenesByOrthologPattern":
        parameters = await _auto_expand_organism_param(
            site_id, record_type or "transcript", parameters
        )

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
        return StepCreationResult(step=None, step_id=None, error=error)

    # Validate root status for input steps.
    if (
        primary_input is not None
        and primary_input_step_id is not None
        and primary_input_step_id not in graph.roots
    ):
        root_error = _validate_root_status(graph, primary_input_step_id, "primary")
        if root_error is not None:
            return StepCreationResult(step=None, step_id=None, error=root_error)
    if (
        secondary_input is not None
        and secondary_input_step_id is not None
        and secondary_input_step_id not in graph.roots
    ):
        root_error = _validate_root_status(graph, secondary_input_step_id, "secondary")
        if root_error is not None:
            return StepCreationResult(step=None, step_id=None, error=root_error)

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
            return StepCreationResult(
                step=None,
                step_id=None,
                error=tool_error(
                    ErrorCode.INVALID_STRATEGY,
                    "search_name is required for leaf and transform steps.",
                    graphId=graph.id,
                ),
            )

    # Validate leaf steps (no inputs).
    if primary_input is None and secondary_input is None:
        leaf_error = await _validate_leaf_step(
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
        if leaf_error is not None:
            return StepCreationResult(step=None, step_id=None, error=leaf_error)

    # Validate transform steps (primary input only, no secondary).
    if primary_input is not None and secondary_input is None:
        transform_error = await _validate_transform_step(
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
        if transform_error is not None:
            return StepCreationResult(step=None, step_id=None, error=transform_error)

    # Parse operator and build colocation params.
    op = parse_op(operator) if secondary_input is not None and operator else None
    colocation = _build_colocation_params(op, upstream, downstream, strand)

    # Build and add the step.
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
    return StepCreationResult(step=step, step_id=step_id, error=None)
