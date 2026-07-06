"""Kind-specific step validation — leaf, transform, and binary combine.

Validates steps by kind: fold-change sample guards for leaves, input-step
parameter checks for transforms, cross-organism INTERSECT guards for
binary combines, and the top-level search-name resolution + dispatch.
"""

from typing import cast

from pydantic import JsonValue

from pathfinder.domain.parameters.specs import find_input_step_param
from pathfinder.domain.parameters.values import ParamValue, to_decoded_map
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp, parse_op
from pathfinder.domain.strategy.organism import extract_output_organisms
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
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
    parameters: dict[str, ParamValue],
    is_transform: bool,
    callbacks: ValidationCallbacks,
) -> tuple[dict[str, ParamValue], ToolErrorPayload | None]:
    """Validate a leaf or transform step.

    Returns (canonical_parameters, error_or_none). ``canonical_parameters``
    is the validator's vocab-matched, decoded-form output — pass it to
    ``StrategyStepNode(parameters=...)``.

    Shared validation (search resolution + parameter validation) runs first,
    then kind-specific checks:
    - Leaf: fold-change duplicate sample guard.
    - Transform: confirm the search accepts an input step.

    Callers must invoke ``_resolve_and_set_record_type`` before this function;
    the resolved type is read from ``graph.record_type``.
    """
    resolved_record_type = graph.record_type or "transcript"
    rt, canonical, error = await resolve_search_and_validate_params(
        graph=graph,
        site_id=site_id,
        resolved_record_type=resolved_record_type,
        search_name=search_name,
        parameters=parameters,
        callbacks=callbacks,
    )
    if error is not None:
        return canonical, error

    if is_transform:
        return canonical, await _validate_transform_input_param(
            rt, site_id, search_name
        )

    # Leaf-specific: a differential search whose reference and comparison
    # sample groups are identical compares a group to itself → 0 results.
    return canonical, _validate_contrast_samples(search_name, canonical)


def _validate_contrast_samples(
    search_name: str,
    parameters: dict[str, ParamValue],
) -> ToolErrorPayload | None:
    """Guard against identical reference/comparison samples in a differential
    search. Covers any ``*_ref_*`` / ``*_comp_*`` sample pair (fold-change
    ``samples_fc_*``, DESeq ``samples_de_*``, …) plus the percentile-vs-comp
    variant. A contrast of a group against itself yields zero results."""
    decoded = to_decoded_map(parameters)
    for ref_name, ref_value in decoded.items():
        if "_ref_" not in ref_name:
            continue
        comp_value = decoded.get(ref_name.replace("_ref_", "_comp_"))
        if ref_value and comp_value and str(ref_value) == str(comp_value):
            return _identical_samples_error(search_name, ref_value, comp_value)
    percentile = decoded.get("samples_percentile_generic")
    comp = decoded.get("samples_fc_comp_generic")
    if percentile and comp and str(percentile) == str(comp):
        return _identical_samples_error(search_name, percentile, comp)
    return None


def _identical_samples_error(
    search_name: str, ref: JsonValue, comp: JsonValue
) -> ToolErrorPayload:
    return tool_error(
        ErrorCode.VALIDATION_ERROR,
        "Reference and comparison samples are identical — this will produce "
        "meaningless differential-expression results. Set different samples "
        "for reference vs comparison.",
        searchName=search_name,
        ref=ref,
        comp=comp,
    )


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
) -> tuple[dict[str, ParamValue], ToolErrorPayload | None]:
    """Validate a step based on its kind. Returns (canonical_params, error)."""
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
    binary_error = (
        _validate_cross_organism_intersect(graph, inputs.primary, inputs.secondary)
        if parsed_op == CombineOp.INTERSECT and inputs.primary and inputs.secondary
        else None
    )
    return inputs.params or {}, binary_error


async def resolve_search_name_and_validate(
    *,
    graph: StrategyGraph,
    site_id: str,
    spec_search_name: str | None,
    inputs: StepInputs,
    callbacks: ValidationCallbacks,
    combine_placeholder: str,
) -> tuple[str, CombineOp | None, dict[str, ParamValue], ToolErrorPayload | None]:
    """Resolve search_name, parse operator, and run step validation.

    :returns: (search_name, parsed_op, canonical_parameters, error_or_none).
        ``canonical_parameters`` is the validator's vocab-matched output;
        bind it to the new ``StrategyStepNode`` so the AST holds canonical
        decoded values.
    """
    is_binary = inputs.primary is not None and inputs.secondary is not None
    search_name, name_error = _resolve_search_name(
        graph,
        spec_search_name,
        is_binary=is_binary,
        combine_placeholder=combine_placeholder,
    )
    if name_error is not None:
        return search_name, None, inputs.params or {}, name_error

    parsed_op = (
        parse_op(inputs.operator)
        if inputs.secondary is not None and inputs.operator
        else None
    )
    canonical, step_error = await _validate_step_by_kind(
        graph=graph,
        site_id=site_id,
        search_name=search_name,
        inputs=inputs,
        parsed_op=parsed_op,
        callbacks=callbacks,
    )
    return search_name, parsed_op, canonical, step_error
