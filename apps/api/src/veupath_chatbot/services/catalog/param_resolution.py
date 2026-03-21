"""WDK parameter fetching, caching, and expansion."""

from typing import cast

import httpx

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
    find_input_step_param,
    unwrap_search_data,
)
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.param_utils import normalize_param_value
from veupath_chatbot.platform.errors import AppError, ErrorCode, WDKError
from veupath_chatbot.platform.errors import ValidationError as CoreValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.catalog.param_discovery import fetch_search_details
from veupath_chatbot.services.catalog.param_formatting import format_param_info
from veupath_chatbot.services.wdk.record_types import resolve_record_type

from .searches import find_record_type_for_search

logger = get_logger(__name__)

_MIN_VOCAB_ENTRY_LENGTH = 2
# Cap phyletic tree matches to keep the tool response concise for the LLM
# and avoid overwhelming it with hundreds of species/clade entries.
_MAX_TREE_MATCHES = 20

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_search_parameters(ctx: SearchContext) -> JSONObject:
    """Get detailed parameter info for a specific search.

    This is intentionally defensive: WDK responses can vary by site/endpoint.
    """
    discovery = get_discovery_service()
    resolved_record_type = ctx.record_type

    record_types = await discovery.get_record_types(ctx.site_id)

    if ctx.record_type:
        resolved = resolve_record_type(record_types, ctx.record_type)
        if resolved:
            resolved_record_type = resolved

    resolved_ctx = SearchContext(ctx.site_id, resolved_record_type, ctx.search_name)
    details, resolved_record_type = await fetch_search_details(
        discovery,
        resolved_ctx,
        record_types=record_types,
    )

    details = unwrap_search_data(details) or details
    param_specs = extract_param_specs(details if isinstance(details, dict) else {})
    param_info = format_param_info(param_specs)

    details_display_name = ctx.search_name
    details_description = ""
    if isinstance(details, dict):
        display_name_raw = details.get("displayName")
        if isinstance(display_name_raw, str):
            details_display_name = display_name_raw
        description_raw = details.get("description")
        if isinstance(description_raw, str):
            details_description = description_raw

    return {
        "searchName": ctx.search_name,
        "displayName": details_display_name,
        "description": details_description,
        "parameters": param_info,
        "resolvedRecordType": resolved_record_type,
    }


async def get_search_parameters_tool(ctx: SearchContext) -> JSONObject:
    """Tool-friendly wrapper that returns standardized tool_error payloads."""
    try:
        return await get_search_parameters(ctx)
    except CoreValidationError as exc:
        code = None
        if exc.errors and isinstance(exc.errors, list) and exc.errors:
            first_error = exc.errors[0]
            if isinstance(first_error, dict):
                code_raw = first_error.get("code")
                if isinstance(code_raw, str):
                    code = code_raw
        return tool_error(
            code or ErrorCode.VALIDATION_ERROR,
            exc.detail or exc.title,
            errors=exc.errors,
        )


async def lookup_phyletic_codes(
    site_id: str,
    record_type: str,
    query: str,
) -> JSONObject:
    """Search phyletic species codes by name for the GenesByOrthologPattern search.

    Returns matching ``{code, label}`` pairs from the ``phyletic_term_map``
    vocabulary. The model uses codes to build ``profile_pattern`` values.

    :param site_id: Site ID.
    :param record_type: Record type (usually "transcript").
    :param query: Species/clade name search term (case-insensitive substring).
    :returns: Dict with ``matches`` list and ``query`` echo.
    """
    try:
        discovery = get_discovery_service()
        record_types = await discovery.get_record_types(site_id)
        resolved = resolve_record_type(record_types, record_type) or record_type

        details, _ = await fetch_search_details(
            discovery,
            SearchContext(site_id, resolved, "GenesByOrthologPattern"),
            record_types=record_types,
        )
        details = unwrap_search_data(details) or details
        specs = extract_param_specs(details if isinstance(details, dict) else {})

        term_map_vocab: JSONArray = []
        indent_map_vocab: JSONArray = []
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            name = spec.get("name")
            if name == "phyletic_term_map":
                vocab = spec.get("vocabulary")
                if isinstance(vocab, list):
                    term_map_vocab = vocab
            elif name == "phyletic_indent_map":
                vocab = spec.get("vocabulary")
                if isinstance(vocab, list):
                    indent_map_vocab = vocab

        # Build a set of group codes (codes that have children = non-leaf).
        # indent_map entries are [code, depth, null].  A code is a group if
        # the *next* entry has a strictly greater depth.
        group_codes: set[str] = set()
        for i, entry in enumerate(indent_map_vocab):
            if not isinstance(entry, list) or len(entry) < _MIN_VOCAB_ENTRY_LENGTH:
                continue
            code = str(entry[0])
            depth = int(str(entry[1])) if entry[1] is not None else 0
            if i + 1 < len(indent_map_vocab):
                nxt = indent_map_vocab[i + 1]
                if isinstance(nxt, list) and len(nxt) >= _MIN_VOCAB_ENTRY_LENGTH:
                    next_depth = int(str(nxt[1])) if nxt[1] is not None else 0
                    if next_depth > depth:
                        group_codes.add(code)

        q = query.lower().strip()
        matches: list[JSONObject] = []
        for entry in term_map_vocab:
            if not isinstance(entry, list) or len(entry) < _MIN_VOCAB_ENTRY_LENGTH:
                continue
            code = str(entry[0])
            label = str(entry[1])
            if code == "ALL":
                continue
            if q in label.lower() or q in code.lower():
                is_leaf = code not in group_codes
                matches.append({"code": code, "label": label, "leaf": is_leaf})
                if len(matches) >= _MAX_TREE_MATCHES:
                    break

        return {
            "query": query,
            "matches": cast("JSONValue", matches),
            "total": len(matches),
            "hint": (
                "Use codes in profile_pattern: %CODE:Y% (include) or %CODE:N% (exclude). "
                "Example: '%MAMM:N%pfal:Y%'. "
                "Group codes (leaf=false) support optional quantifier: "
                "MAMM:N:all (absent from all, default for :N), "
                "APIC:Y:any (present in any, default for :Y). "
                "Leaf codes need no quantifier."
            ),
        }
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
        return tool_error(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to look up phyletic codes: {exc}",
        )


async def expand_search_details_with_params(
    ctx: SearchContext,
    context_values: JSONObject | None,
) -> JSONObject:
    """Return WDK search details after applying (WDK-wire) context values.

    NOTE: despite the historical name, this is *not* a pure validation API; it returns
    WDK search details payload. Keep it separate from the public validation endpoint.
    """
    client = get_wdk_client(ctx.site_id)
    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    details: JSONObject | None = None
    allowed: set[str] = set()
    details, allowed = await _load_discovery_details_and_allowed(ctx)
    filtered_context = _filter_context_values(raw_context, allowed)

    details_unwrapped = unwrap_search_data(details)
    specs = adapt_param_specs(details_unwrapped) if details_unwrapped else {}

    if specs:
        normalizer = ParameterNormalizer(specs)
        try:
            normalized_context = normalizer.normalize(filtered_context)
        except CoreValidationError:
            resolved_record_type = await find_record_type_for_search(ctx)
            details = await client.get_search_details_with_params(
                resolved_record_type,
                ctx.search_name,
                filtered_context,
                expand_params=True,
            )
            details = unwrap_search_data(details) or details
            specs = adapt_param_specs(details if isinstance(details, dict) else {})
            normalizer = ParameterNormalizer(specs)
            normalized_context = normalizer.normalize(filtered_context)
        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized_context[input_step_param] = ""
    else:
        normalized_context = {
            key: normalize_param_value(value) for key, value in filtered_context.items()
        }
    resolved_record_type = await find_record_type_for_search(ctx)
    return await _get_search_details_with_portal_fallback(
        site_id=ctx.site_id,
        client=client,
        record_type=resolved_record_type,
        search_name=ctx.search_name,
        context_values=normalized_context,
    )


def _filter_context_values(raw_context: JSONObject, allowed: set[str]) -> JSONObject:
    """Filter context values to keys WDK recognizes for the search (best-effort).

    :param raw_context: Raw context from request.
    :param allowed: Set of allowed parameter names.
    :returns: Filtered context dict.
    """
    return (
        {key: value for key, value in raw_context.items() if key in allowed}
        if allowed
        else dict(raw_context)
    )


async def _load_discovery_details_and_allowed(
    ctx: SearchContext,
) -> tuple[JSONObject | None, set[str]]:
    """Load discovery search details + extract allowed param names (best-effort)."""
    try:
        discovery = get_discovery_service()
        details = await discovery.get_search_details(
            ctx, expand_params=True
        )
        return (
            details,
            _extract_param_names(details if isinstance(details, dict) else {}),
        )
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "Failed to load discovery details for param resolution",
            site_id=ctx.site_id,
            record_type=ctx.record_type,
            search_name=ctx.search_name,
            error=str(exc),
        )
        return None, set()


async def _get_search_details_with_portal_fallback(
    *,
    site_id: str,
    client: VEuPathDBClient,
    record_type: str,
    search_name: str,
    context_values: JSONObject,
) -> JSONObject:
    """Call WDK contextual search details, falling back to portal when appropriate."""
    try:
        return await client.get_search_details_with_params(
            record_type,
            search_name,
            context_values,
        )
    except WDKError:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_search_details_with_params(
                record_type,
                search_name,
                context_values,
            )
        raise


async def get_refreshed_dependent_params(
    ctx: SearchContext,
    *,
    parameter_name: str,
    context_values: JSONObject,
) -> JSONObject:
    """Get refreshed dependent parameter vocabulary, falling back to the portal.

    Tries the site-specific WDK client first.  If that fails with a
    ``WDKError`` and the site is not already ``veupathdb``, retries against
    the portal client (``veupathdb``).
    """
    client = get_wdk_client(ctx.site_id)
    try:
        return await client.get_refreshed_dependent_params(
            ctx.record_type,
            ctx.search_name,
            parameter_name,
            context_values,
        )
    except WDKError:
        if ctx.site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_refreshed_dependent_params(
                ctx.record_type,
                ctx.search_name,
                parameter_name,
                context_values,
            )
        raise


def _names_from_param_list(params: list[JSONValue]) -> set[str]:
    """Extract name strings from a list of param dicts."""
    names: set[str] = set()
    for p in params:
        if isinstance(p, dict):
            name = p.get("name")
            if isinstance(name, str):
                names.add(name)
    return names


def _extract_param_names(details: JSONObject) -> set[str]:
    """Extract parameter names from WDK search details.

    Checks ``details.searchData.parameters`` first, then ``details.parameters``.
    """
    if not isinstance(details, dict):
        return set()
    unwrapped = unwrap_search_data(details) or details
    params = unwrapped.get("parameters") if isinstance(unwrapped, dict) else None
    if isinstance(params, list):
        return _names_from_param_list(params)
    if isinstance(params, dict):
        return {k for k in params if k}
    return set()
