"""Kind-specific step validation — leaf, transform, and binary combine.

Validates steps by kind: fold-change sample guards for leaves, input-step
parameter checks for transforms, cross-organism INTERSECT guards for
binary combines, and the top-level search-name resolution + dispatch.
"""

from typing import cast

from pydantic import JsonValue

from pathfinder.domain.parameters.specs import find_input_step_param
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp, parse_op
from pathfinder.domain.strategy.organism import extract_output_organisms
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search
from pathfinder.services.catalog.param_validation import ValidationCallbacks
from pathfinder.services.strategies.input_resolution import StepInputs
from pathfinder.services.strategies.search_resolution import (
    resolve_search_and_validate_params,
)


async def _validate_leaf_or_transform(
    *,
    graph: StrategyGraph,
    site_id: str,
    search_name: str,
    parameters: JSONObject,
    is_transform: bool,
    callbacks: ValidationCallbacks,
) -> ToolErrorPayload | None:
    """Validate a leaf or transform step.

    Returns error payload or None on success.

    Shared validation (search resolution + parameter validation) runs first,
    then kind-specific checks:
    - Leaf: fold-change duplicate sample guard.
    - Transform: confirm the search accepts an input step.

    Callers must invoke ``_resolve_and_set_record_type`` before this function;
    the resolved type is read from ``graph.record_type``.
    """
    resolved_record_type = graph.record_type or "transcript"
    rt, error = await resolve_search_and_validate_params(
        graph=graph,
        site_id=site_id,
        resolved_record_type=resolved_record_type,
        search_name=search_name,
        parameters=parameters,
        callbacks=callbacks,
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
) -> ToolErrorPayload | None:
    """Guard against identical ref/comp samples in fold-change searches."""
    ref = parameters.get("samples_fc_ref_generic") or parameters.get(
        "samples_percentile_generic"
    )
    comp = parameters.get("samples_fc_comp_generic")
    if ref and comp and str(ref) == str(comp):
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Reference and comparison samples are identical — this "
            "will produce meaningless fold-change results. Set "
            "different samples for reference vs comparison.",
            searchName=search_name,
            ref=ref,
            comp=comp,
        )
    return None

async def _validate_transform_input_param(
    rt: str,
    site_id: str,
    search_name: str,
) -> ToolErrorPayload | None:
    """Confirm the search accepts an input step (required for transforms)."""
    try:
        wdk = get_wdk_client(site_id)
        response = await wdk.get_search_details(rt, search_name, expand_params=True)
    except AppError as exc:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Failed to load search metadata for transform validation.",
            recordType=rt,
            searchName=search_name,
            detail=str(exc),
        )
    specs = adapt_param_specs_from_search(response.search_data)
    input_param = find_input_step_param(specs)
    if not input_param:
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            f"Search '{search_name}' cannot be used as a transform: "
            "it does not accept an input step. "
            f"Call list_transforms(record_type='{rt}') to see available "
            "transforms (e.g. GenesByOrthologs for ortholog "
            "conversion).",
            recordType=rt,
            searchName=search_name,
            suggestedFix={
                "message": (
                    "Call list_transforms() to find the correct "
                    "transform search, or create this as a leaf step "
                    "and combine with INTERSECT/UNION/MINUS."
                ),
                "asLeaf": {
                    "searchName": search_name,
                    "recordType": rt,
                },
            },
        )

    # Check that the input step's record type is accepted by this transform.
    allowed = response.search_data.allowed_primary_input_record_class_names
    if allowed and rt not in allowed:
        allowed_str = ", ".join(allowed)
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            f"Search '{search_name}' requires input of type "
            f"{allowed_str}, but the current graph has record type "
            f"'{rt}'. This transform cannot be applied to the "
            f"current step.",
            recordType=rt,
            searchName=search_name,
            allowedInputTypes=cast("JsonValue", allowed),
        )
    return None

def _validate_cross_organism_intersect(
    graph: StrategyGraph,
    primary_input: StrategyStepNode,
    secondary_input: StrategyStepNode,
) -> ToolErrorPayload | None:
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
            "Cannot INTERSECT steps with different organism scopes "
            f"({', '.join(sorted(primary_orgs))} vs "
            f"{', '.join(sorted(secondary_orgs))}). "
            "Gene IDs from different species never match, so this "
            "always returns 0 results. "
            "Apply organism-specific filters BEFORE any ortholog "
            "transform, not after.",
            graphId=graph.id,
            primaryOrganisms=cast("JsonValue", sorted(primary_orgs)),
            secondaryOrganisms=cast("JsonValue", sorted(secondary_orgs)),
        )
    return None

def _resolve_search_name(
    graph: StrategyGraph,
    spec_search_name: str | None,
    *,
    is_binary: bool,
    combine_placeholder: str,
) -> tuple[str, ToolErrorPayload | None]:
    """Resolve the effective search name, returning (name, error_or_none)."""
    if spec_search_name:
        return spec_search_name, None
    if is_binary:
        return combine_placeholder, None
    return "", tool_error(
        ErrorCode.INVALID_STRATEGY,
        "search_name is required for leaf and transform steps.",
        graphId=graph.id,
    )

async def _validate_step_by_kind(
    *,
    graph: StrategyGraph,
    site_id: str,
    search_name: str,
    inputs: StepInputs,
    parsed_op: CombineOp | None,
    callbacks: ValidationCallbacks,
) -> ToolErrorPayload | None:
    """Validate a step based on its kind (leaf/transform vs binary)."""
    is_binary = inputs.primary is not None and inputs.secondary is not None
    if not is_binary:
        return await _validate_leaf_or_transform(
            graph=graph,
            site_id=site_id,
            search_name=search_name,
            parameters=inputs.params or {},
            is_transform=inputs.primary is not None,
            callbacks=callbacks,
        )
    return (
        _validate_cross_organism_intersect(graph, inputs.primary, inputs.secondary)
        if parsed_op == CombineOp.INTERSECT and inputs.primary and inputs.secondary
        else None
    )

async def resolve_search_name_and_validate(
    *,
    graph: StrategyGraph,
    site_id: str,
    spec_search_name: str | None,
    inputs: StepInputs,
    callbacks: ValidationCallbacks,
    combine_placeholder: str,
) -> tuple[str, CombineOp | None, ToolErrorPayload | None]:
    """Resolve search_name, parse operator, and run step validation.

    :returns: (search_name, parsed_op, error_or_none).
    """
    is_binary = inputs.primary is not None and inputs.secondary is not None
    search_name, name_error = _resolve_search_name(
        graph,
        spec_search_name,
        is_binary=is_binary,
        combine_placeholder=combine_placeholder,
    )
    if name_error is not None:
        return search_name, None, name_error

    parsed_op = (
        parse_op(inputs.operator)
        if inputs.secondary is not None and inputs.operator
        else None
    )
    step_error = await _validate_step_by_kind(
        graph=graph,
        site_id=site_id,
        search_name=search_name,
        inputs=inputs,
        parsed_op=parsed_op,
        callbacks=callbacks,
    )
    return search_name, parsed_op, step_error
