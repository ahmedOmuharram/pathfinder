"""Search and record-type resolution for step creation.

Resolves the effective record type (from graph, hint, or search lookup)
and validates parameters against the WDK search metadata.
"""

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.errors import ErrorCode, ValidationError
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.services.catalog.param_validation import (
    ResolveRecordTypeFn,
    ValidationCallbacks,
    validate_parameters,
)


async def resolve_record_type_for_step(
    current: str | None,
    hint: str | None,
    search_name: str | None,
    resolve_record_type_for_search: ResolveRecordTypeFn,
) -> str:
    """Best-effort record type resolution for step creation.

    Tries, in order: *current* (graph's existing type), *hint* (caller-
    supplied), resolver lookup by *search_name*, and finally ``"transcript"``
    as the VEuPathDB default.  Pure — does **not** mutate the graph.
    """
    resolved = current or hint
    if resolved is None and search_name:
        resolved = await resolve_record_type_for_search(
            None, search_name, require_match=False, allow_fallback=True
        )
    return resolved or "transcript"


async def resolve_search_and_validate_params(
    *,
    graph: StrategyGraph,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    parameters: dict[str, ParamValue],
    callbacks: ValidationCallbacks,
) -> tuple[str, dict[str, ParamValue], ToolErrorPayload | None]:
    """Resolve record type for a search and validate its parameters.

    Shared by leaf and transform validation paths.

    :returns: (resolved_record_type, canonical_parameters, error_or_none).
        ``canonical_parameters`` is a fresh dict with vocab-matched,
        decoded-form values; pass it to ``StrategyStepNode(parameters=...)``
        so the AST holds canonical decoded values. ``parameters`` is left
        unmodified.
    """
    rt = await callbacks.resolve_record_type_for_search(
        resolved_record_type,
        search_name,
        require_match=True,
        allow_fallback=True,
    )
    if rt is None:
        record_type_hint = await callbacks.find_record_type_hint(
            search_name, resolved_record_type
        )
        return resolved_record_type, parameters, tool_error(
            ErrorCode.SEARCH_NOT_FOUND,
            f"Unknown or invalid search: {search_name}",
            recordType=resolved_record_type,
            recordTypeHint=record_type_hint,
        )
    # Don't let auxiliary record types (e.g. genomic-segment for DynSpan
    # motif searches used as COLOCATE Set B) overwrite the primary record
    # type.  The graph's record type should stay transcript/gene.
    if graph.record_type is None or rt in ("transcript", "gene"):
        graph.record_type = rt

    try:
        canonical = await validate_parameters(
            SearchContext(site_id, rt, search_name),
            parameters=parameters,
            callbacks=callbacks,
        )
    except ValidationError as exc:
        error_fn = callbacks.validation_error_payload
        if error_fn is None:
            raise
        return rt, parameters, error_fn(exc)

    return rt, canonical, None
