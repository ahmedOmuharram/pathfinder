"""WDK parameter fetching, caching, and expansion."""

from typing import Any, cast

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
    find_input_step_param,
    unwrap_search_data,
)
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.param_utils import (
    normalize_param_value,
    wdk_entity_name,
    wdk_search_matches,
)
from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.errors import ValidationError as CoreValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.wdk.record_types import resolve_record_type

from .searches import find_record_type_for_search

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Extracted helpers
# ---------------------------------------------------------------------------


def _allowed_values(
    vocab: JSONObject | JSONArray | None,
) -> list[JSONObject]:
    """Extract WDK-accepted parameter values from a vocabulary.

    Returns ``[{"value": <wdk_value>, "display": <label>}, ...]`` so the LLM
    knows both *what to pass* and *what it means*.

    :param vocab: Vocabulary tree or flat list from catalog.
    :returns: List of value/display dicts (capped at 50).
    """
    if not vocab:
        return []
    entries: list[JSONObject] = []
    seen: set[str] = set()
    for entry in flatten_vocab(vocab, prefer_term=True):
        # Prefer the WDK-accepted value; fall back to display if missing.
        candidate = entry.get("value") or entry.get("display")
        if not candidate:
            continue
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        display = entry.get("display")
        display_str = str(display) if display else text
        entries.append({"value": text, "display": display_str})
        if len(entries) >= 50:
            break
    return entries


_PHYLETIC_STRUCTURAL_PARAMS = frozenset({"phyletic_indent_map", "phyletic_term_map"})

_PROFILE_PATTERN_HELP = (
    "Phylogenetic profile pattern. Format: %CODE:STATE[:QUANTIFIER]% (percent-delimited).\n"
    "  CODE  = species or group code from lookup_phyletic_codes()\n"
    "  STATE = Y (present) or N (absent)\n"
    "  QUANTIFIER = 'any' or 'all' (optional, only matters for group codes)\n"
    "\n"
    "For leaf species codes (e.g. pfal, hsap), quantifier is ignored:\n"
    "  pfal:Y  → present in P. falciparum\n"
    "  hsap:N  → absent from H. sapiens\n"
    "\n"
    "For group codes (e.g. MAMM, APIC), quantifier controls expansion:\n"
    "  MAMM:N       → absent from ALL mammals (default for :N)\n"
    "  MAMM:N:all   → same as above (explicit)\n"
    "  APIC:Y:any   → present in ANY Apicomplexa (default for :Y, dropped from pattern)\n"
    "  APIC:Y:all   → present in ALL Apicomplexa (expanded, usually 0 results)\n"
    "\n"
    "Example: '%MAMM:N%pfal:Y%' → P.falciparum present, all mammals absent\n"
    "\n"
    "CRITICAL: The 'organism' parameter controls which organisms' genes appear in "
    "results. You MUST select ALL relevant organisms (use all leaf values from the "
    "organism vocabulary tree, or use the tree's root '@@fake@@' sentinel for 'select all'). "
    "If you only select one organism, you will get 0 results even if the pattern is correct."
)


def _format_param_info(param_specs: JSONArray) -> JSONArray:
    """Build a formatted parameter info array from raw WDK param specs.

    Each spec dict is transformed into a normalized info dict with keys:
    name, displayName, type, required, isVisible, help, and optionally
    allowedValues and defaultValue.

    Phyletic structural params (phyletic_indent_map, phyletic_term_map) are
    omitted from AI tool output — the model should never set them directly.
    The profile_pattern param gets enriched help text with encoding docs.

    :param param_specs: Raw parameter spec dicts from WDK.
    :returns: Formatted parameter info array.
    """
    param_info: JSONArray = []
    for spec in param_specs:
        if not isinstance(spec, dict):
            continue
        name_raw = spec.get("name")
        name = name_raw if isinstance(name_raw, str) else ""
        if not name:
            continue

        # Skip phyletic structural params — model should not set these.
        if name in _PHYLETIC_STRUCTURAL_PARAMS:
            continue

        allow_empty_raw = spec.get("allowEmptyValue")
        required = not bool(allow_empty_raw)

        display_name_raw = spec.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else name
        type_raw = spec.get("type")
        param_type = type_raw if isinstance(type_raw, str) else "string"
        help_raw = spec.get("help")
        help_text = help_raw if isinstance(help_raw, str) else ""
        is_visible_raw = spec.get("isVisible")
        is_visible = is_visible_raw if isinstance(is_visible_raw, bool) else True

        # Inject enriched help for profile_pattern.
        if name == "profile_pattern":
            help_text = _PROFILE_PATTERN_HELP

        info: JSONObject = {
            "name": name,
            "displayName": display_name,
            "type": param_type,
            "required": required,
            "isVisible": is_visible,
            "help": help_text,
        }

        vocabulary_raw = spec.get("vocabulary")
        vocabulary = (
            vocabulary_raw if isinstance(vocabulary_raw, (dict, list)) else None
        )
        allowed_entries = _allowed_values(vocabulary)
        if allowed_entries:
            info["allowedValues"] = cast(JSONValue, allowed_entries)

        initial_display_raw = spec.get("initialDisplayValue")
        if initial_display_raw is not None:
            info["defaultValue"] = initial_display_raw
        default_value_raw = spec.get("defaultValue")
        if default_value_raw is not None and "defaultValue" not in info:
            info["defaultValue"] = default_value_raw

        param_info.append(info)
    return param_info


async def _fetch_search_details(
    discovery: Any,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    *,
    record_types: list[Any] | None = None,
) -> tuple[JSONObject, str]:
    """Fetch search details, falling back to scanning all record types.

    :param discovery: Discovery service instance.
    :param site_id: Site identifier.
    :param resolved_record_type: Record type to try first.
    :param search_name: Name of the search.
    :param record_types: All available record types (for fallback scan).
    :returns: Tuple of (details dict, resolved record type).
    :raises CoreValidationError: When the search cannot be found.
    """
    try:
        details = await discovery.get_search_details(
            site_id, resolved_record_type, search_name, expand_params=True
        )
        return details, resolved_record_type
    except Exception as e:
        return await _fallback_scan_record_types(
            discovery,
            site_id,
            resolved_record_type,
            search_name,
            record_types=record_types or [],
            original_error=e,
        )


async def _fallback_scan_record_types(
    discovery: Any,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    *,
    record_types: list[Any],
    original_error: Exception,
) -> tuple[JSONObject, str]:
    """Scan all record types trying to find the search, raising if not found."""
    details: JSONObject | None = None
    for rt in record_types:
        if not isinstance(rt, dict):
            continue
        rt_name = wdk_entity_name(rt)
        if not rt_name:
            continue
        searches = await discovery.get_searches(site_id, rt_name)
        if any(wdk_search_matches(s, search_name) for s in searches):
            resolved_record_type = rt_name
            try:
                details = await discovery.get_search_details(
                    site_id, rt_name, search_name, expand_params=True
                )
            except Exception:
                details = None
            break

    if details is None:
        available = await discovery.get_searches(site_id, resolved_record_type)
        available_searches: list[str] = [
            name
            for s in available
            if isinstance(s, dict) and (name := wdk_entity_name(s))
        ]
        error_dict: JSONObject = {
            "path": "searchName",
            "message": f"Search not found: {search_name}",
            "code": ErrorCode.SEARCH_NOT_FOUND.value,
            "recordType": resolved_record_type,
            "searchName": search_name,
            "availableSearches": cast(JSONValue, available_searches),
            "details": str(original_error),
        }
        raise CoreValidationError(
            title="Search not found",
            detail=f"Search not found: {search_name}",
            errors=[error_dict],
        ) from original_error

    return details, resolved_record_type


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_search_parameters(
    site_id: str,
    record_type: str,
    search_name: str,
) -> JSONObject:
    """Get detailed parameter info for a specific search.

    This is intentionally defensive: WDK responses can vary by site/endpoint.
    """
    discovery = get_discovery_service()
    resolved_record_type = record_type

    record_types = await discovery.get_record_types(site_id)

    if record_type:
        resolved = resolve_record_type(record_types, record_type)
        if resolved:
            resolved_record_type = resolved

    details, resolved_record_type = await _fetch_search_details(
        discovery,
        site_id,
        resolved_record_type,
        search_name,
        record_types=record_types,
    )

    details = unwrap_search_data(details) or details
    param_specs = extract_param_specs(details if isinstance(details, dict) else {})
    param_info = _format_param_info(param_specs)

    details_display_name = search_name
    details_description = ""
    if isinstance(details, dict):
        display_name_raw = details.get("displayName")
        if isinstance(display_name_raw, str):
            details_display_name = display_name_raw
        description_raw = details.get("description")
        if isinstance(description_raw, str):
            details_description = description_raw

    return {
        "searchName": search_name,
        "displayName": details_display_name,
        "description": details_description,
        "parameters": param_info,
        "resolvedRecordType": resolved_record_type,
    }


async def get_search_parameters_tool(
    site_id: str,
    record_type: str,
    search_name: str,
) -> JSONObject:
    """Tool-friendly wrapper that returns standardized tool_error payloads."""
    try:
        return await get_search_parameters(site_id, record_type, search_name)
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

        details, _ = await _fetch_search_details(
            discovery,
            site_id,
            resolved,
            "GenesByOrthologPattern",
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
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            code = str(entry[0])
            depth = int(str(entry[1])) if entry[1] is not None else 0
            if i + 1 < len(indent_map_vocab):
                nxt = indent_map_vocab[i + 1]
                if isinstance(nxt, list) and len(nxt) >= 2:
                    next_depth = int(str(nxt[1])) if nxt[1] is not None else 0
                    if next_depth > depth:
                        group_codes.add(code)

        q = query.lower().strip()
        matches: list[JSONObject] = []
        for entry in term_map_vocab:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            code = str(entry[0])
            label = str(entry[1])
            if code == "ALL":
                continue
            if q in label.lower() or q in code.lower():
                is_leaf = code not in group_codes
                matches.append({"code": code, "label": label, "leaf": is_leaf})
                if len(matches) >= 20:
                    break

        return {
            "query": query,
            "matches": cast(JSONValue, matches),
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
    except Exception as exc:
        return tool_error(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to look up phyletic codes: {exc}",
        )


async def expand_search_details_with_params(
    site_id: str,
    record_type: str,
    search_name: str,
    context_values: JSONObject | None,
) -> JSONObject:
    """Return WDK search details after applying (WDK-wire) context values.

    NOTE: despite the historical name, this is *not* a pure validation API; it returns
    WDK search details payload. Keep it separate from the public validation endpoint.
    """
    client = get_wdk_client(site_id)
    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    details: JSONObject | None = None
    allowed: set[str] = set()
    details, allowed = await _load_discovery_details_and_allowed(
        site_id=site_id,
        record_type=record_type,
        search_name=search_name,
    )
    filtered_context = _filter_context_values(raw_context, allowed)

    details_unwrapped = unwrap_search_data(details)
    specs = adapt_param_specs(details_unwrapped) if details_unwrapped else {}

    if specs:
        normalizer = ParameterNormalizer(specs)
        try:
            normalized_context = normalizer.normalize(filtered_context)
        except CoreValidationError:
            try:
                resolved_record_type = await find_record_type_for_search(
                    site_id, record_type, search_name
                )
                details = await client.get_search_details_with_params(
                    resolved_record_type,
                    search_name,
                    filtered_context,
                    expand_params=True,
                )
            except Exception:
                raise
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
    resolved_record_type = await find_record_type_for_search(
        site_id, record_type, search_name
    )
    return await _get_search_details_with_portal_fallback(
        site_id=site_id,
        client=client,
        record_type=resolved_record_type,
        search_name=search_name,
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
    *, site_id: str, record_type: str, search_name: str
) -> tuple[JSONObject | None, set[str]]:
    """Load discovery search details + extract allowed param names (best-effort)."""
    try:
        discovery = get_discovery_service()
        details = await discovery.get_search_details(
            site_id, record_type, search_name, expand_params=True
        )
        return (
            details,
            _extract_param_names(details if isinstance(details, dict) else {}),
        )
    except Exception as exc:
        logger.warning(
            "Failed to load discovery details for param resolution",
            site_id=site_id,
            record_type=record_type,
            search_name=search_name,
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
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameter_name: str,
    context_values: JSONObject,
) -> JSONObject:
    """Get refreshed dependent parameter vocabulary, falling back to the portal.

    Tries the site-specific WDK client first.  If that fails with a
    ``WDKError`` and the site is not already ``veupathdb``, retries against
    the portal client (``veupathdb``).

    :param site_id: Site identifier.
    :param record_type: WDK record type.
    :param search_name: WDK search name.
    :param parameter_name: The dependent parameter to refresh.
    :param context_values: Current context parameter values.
    :returns: Refreshed dependent param payload from WDK.
    """
    client = get_wdk_client(site_id)
    try:
        return await client.get_refreshed_dependent_params(
            record_type,
            search_name,
            parameter_name,
            context_values,
        )
    except WDKError:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_refreshed_dependent_params(
                record_type,
                search_name,
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
