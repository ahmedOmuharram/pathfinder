"""Search parameter retrieval, validation, and expansion functions."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
    find_input_step_param,
)
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.errors import ValidationError as CoreValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

from .searches import _resolve_record_type_for_search


async def get_search_parameters(
    site_id: str,
    record_type: str,
    search_name: str,
) -> JSONObject:
    """Get detailed parameter info for a specific search.

    This is intentionally defensive: WDK responses can vary by site/endpoint.
    """
    discovery = get_discovery_service()
    details: JSONObject | None = None
    resolved_record_type = record_type

    record_types = await discovery.get_record_types(site_id)

    def normalize(value: str) -> str:
        return value.strip().lower()

    if record_type:
        normalized = normalize(record_type)
        exact: list[JSONObject] = []
        for rt in record_types:
            if not isinstance(rt, dict):
                continue
            url_seg_raw = rt.get("urlSegment")
            name_raw = rt.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else ""
            if normalize(url_seg or name) == normalized:
                exact.append(rt)
        if exact:
            first = exact[0]
            exact_url_seg_raw = first.get("urlSegment")
            exact_name_raw = first.get("name")
            exact_url_seg: str | None = (
                exact_url_seg_raw if isinstance(exact_url_seg_raw, str) else None
            )
            exact_name: str | None = (
                exact_name_raw if isinstance(exact_name_raw, str) else None
            )
            new_rt = exact_url_seg or exact_name
            if isinstance(new_rt, str):
                resolved_record_type = new_rt
        else:
            display_matches: list[JSONObject] = []
            for rt in record_types:
                if not isinstance(rt, dict):
                    continue
                display_name_raw = rt.get("displayName")
                display_name = (
                    display_name_raw if isinstance(display_name_raw, str) else ""
                )
                if normalize(display_name) == normalized:
                    display_matches.append(rt)
            if len(display_matches) == 1:
                first = display_matches[0]
                match_url_seg_raw = first.get("urlSegment")
                match_name_raw = first.get("name")
                match_url_seg: str | None = (
                    match_url_seg_raw if isinstance(match_url_seg_raw, str) else None
                )
                match_name: str | None = (
                    match_name_raw if isinstance(match_name_raw, str) else None
                )
                new_rt = match_url_seg or match_name
                if isinstance(new_rt, str):
                    resolved_record_type = new_rt

    try:
        details = await discovery.get_search_details(
            site_id, resolved_record_type, search_name, expand_params=True
        )
    except Exception as e:
        for rt in record_types:
            if not isinstance(rt, dict):
                continue
            url_seg_raw = rt.get("urlSegment")
            name_raw = rt.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else ""
            rt_name = url_seg or name
            if not rt_name:
                continue
            searches = await discovery.get_searches(site_id, rt_name)
            match: JSONObject | None = None
            for s in searches:
                if not isinstance(s, dict):
                    continue
                s_url_seg_raw = s.get("urlSegment")
                s_name_raw = s.get("name")
                s_url_seg = s_url_seg_raw if isinstance(s_url_seg_raw, str) else None
                s_name = s_name_raw if isinstance(s_name_raw, str) else None
                if s_url_seg == search_name or s_name == search_name:
                    match = s
                    break
            if match:
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
            available_searches: list[str] = []
            for s in available:
                if not isinstance(s, dict):
                    continue
                url_seg_raw = s.get("urlSegment")
                name_raw = s.get("name")
                url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
                name = name_raw if isinstance(name_raw, str) else ""
                available_searches.append(url_seg or name)

            error_dict: JSONObject = {
                "path": "searchName",
                "message": f"Search not found: {search_name}",
                "code": ErrorCode.SEARCH_NOT_FOUND.value,
                "recordType": resolved_record_type,
                "searchName": search_name,
                "availableSearches": cast(JSONValue, available_searches),
                "details": str(e),
            }
            raise CoreValidationError(
                title="Search not found",
                detail=f"Search not found: {search_name}",
                errors=[error_dict],
            ) from e

    if isinstance(details, dict):
        search_data_raw = details.get("searchData")
        if isinstance(search_data_raw, dict):
            details = search_data_raw

    param_specs = extract_param_specs(details if isinstance(details, dict) else {})

    def _allowed_values(vocab: JSONObject | JSONArray | None) -> list[str]:
        """Extract WDK-accepted parameter values from a vocabulary.

        Uses term/value (what WDK actually accepts) rather than display labels,
        so the LLM can pass these values directly to WDK API calls without
        needing vocabulary normalisation.

        :param vocab: Vocabulary tree or flat list from catalog.
        :returns: List of WDK-accepted values.
        """
        if not vocab:
            return []
        values: list[str] = []
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
            values.append(text)
            if len(values) >= 50:
                break
        return values

    param_info: JSONArray = []
    for spec in param_specs:
        if not isinstance(spec, dict):
            continue
        # WDK parameter specs use JsonKeys.NAME = "name".
        name_raw = spec.get("name")
        name = name_raw if isinstance(name_raw, str) else ""
        if not name:
            continue
        is_required_raw = spec.get("isRequired")
        if isinstance(is_required_raw, bool):
            required = is_required_raw
        else:
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
        allowed = _allowed_values(vocabulary)
        if allowed:
            info["allowedValues"] = cast(JSONValue, allowed)

        initial_display_raw = spec.get("initialDisplayValue")
        if initial_display_raw is not None:
            info["defaultValue"] = initial_display_raw
        default_value_raw = spec.get("defaultValue")
        if default_value_raw is not None and "defaultValue" not in info:
            info["defaultValue"] = default_value_raw

        param_info.append(info)

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

    details_unwrapped = _unwrap_search_data(details)
    specs = adapt_param_specs(details_unwrapped) if details_unwrapped else {}

    if specs:
        normalizer = ParameterNormalizer(specs)
        try:
            normalized_context = normalizer.normalize(filtered_context)
        except CoreValidationError:
            try:
                resolved_record_type = await _resolve_record_type_for_search(
                    client, record_type, search_name
                )
                details = await client.get_search_details_with_params(
                    resolved_record_type,
                    search_name,
                    filtered_context,
                    expand_params=True,
                )
            except Exception:
                raise
            if isinstance(details, dict):
                search_data_raw = details.get("searchData")
                if isinstance(search_data_raw, dict):
                    details = search_data_raw
            specs = adapt_param_specs(details if isinstance(details, dict) else {})
            normalizer = ParameterNormalizer(specs)
            normalized_context = normalizer.normalize(filtered_context)
        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized_context[input_step_param] = ""
    else:
        normalized_context = {
            key: _normalize_param_value(value)
            for key, value in filtered_context.items()
        }
    resolved_record_type = await _resolve_record_type_for_search(
        client, record_type, search_name
    )
    return await _get_search_details_with_portal_fallback(
        site_id=site_id,
        client=client,
        record_type=resolved_record_type,
        search_name=search_name,
        context_values=normalized_context,
    )


async def validate_search_params(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    context_values: JSONObject | None,
) -> JSONObject:
    """Validate and canonicalize search parameters for UI consumption.

    Returns a stable payload:
      { "validation": { "isValid": bool, "normalizedContextValues": {...}, "errors": {...} } }

    The goal is to keep the frontend a consumer of backend normalization + validation,
    without requiring the UI to interpret raw WDK payloads.
    """
    from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
    from veupath_chatbot.domain.parameters.specs import (
        adapt_param_specs,
        extract_param_specs,
    )
    from veupath_chatbot.platform.errors import ValidationError as AppValidationError

    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    details: JSONObject | None = None
    allowed: set[str] = set()

    try:
        details = await expand_search_details_with_params(
            site_id=site_id,
            record_type=record_type,
            search_name=search_name,
            context_values=raw_context,
        )
        allowed = _extract_param_names(details if isinstance(details, dict) else {})
    except Exception as exc:
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": {},
                "errors": {
                    "general": [f"Failed to load search metadata: {exc}"],
                    "byKey": {},
                },
            }
        }

    filtered_context = _filter_context_values(raw_context, allowed)
    spec_payload = _unwrap_search_data(details) or {}
    spec_map = adapt_param_specs(spec_payload)
    raw_specs = extract_param_specs(spec_payload)

    try:
        canonicalizer = ParameterCanonicalizer(spec_map)
        normalized_context = canonicalizer.canonicalize(filtered_context)
    except AppValidationError as exc:
        by_key: dict[str, list[str]] = {}
        general: list[str] = []
        for err_raw in (exc.errors or []) or []:
            if not isinstance(err_raw, dict):
                continue
            param_raw = err_raw.get("param") or err_raw.get("path")
            param = param_raw if isinstance(param_raw, str) else None
            message_raw = err_raw.get("message") or err_raw.get("detail")
            message = (
                message_raw
                if isinstance(message_raw, str)
                else (exc.detail or exc.title)
            )
            if param:
                by_key.setdefault(param, []).append(message)
            else:
                general.append(str(message))
        if not general:
            general = [exc.detail or exc.title]
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": {},
                "errors": {
                    "general": cast(JSONValue, general),
                    "byKey": cast(JSONValue, by_key),
                },
            }
        }

    # Required checks using raw WDK specs (keeps semantics aligned with WDK).
    required_specs: list[JSONObject] = []
    for p in raw_specs:
        if not isinstance(p, dict):
            continue
        is_required_raw = p.get("isRequired")
        allow_empty_raw = p.get("allowEmptyValue")
        is_required = (
            bool(is_required_raw) if isinstance(is_required_raw, bool) else False
        )
        allow_empty = (
            bool(allow_empty_raw) if isinstance(allow_empty_raw, bool) else True
        )
        if is_required or not allow_empty:
            required_specs.append(p)
    missing: list[str] = []
    for spec in required_specs:
        if not isinstance(spec, dict):
            continue
        name_raw = spec.get("name")
        name = name_raw if isinstance(name_raw, str) else None
        if not name:
            continue
        if name not in normalized_context:
            missing.append(name)
            continue
        value = normalized_context.get(name)
        type_raw = spec.get("type")
        param_type = (type_raw if isinstance(type_raw, str) else "").lower()
        if param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]") or (
                isinstance(value, list) and len(value) == 0
            ):
                missing.append(str(name))
            continue
        if value in (None, "", [], {}):
            missing.append(str(name))

    if missing:
        by_key = {name: ["Required"] for name in missing}
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": normalized_context,
                "errors": {
                    "general": cast(
                        JSONValue,
                        [f"Missing required parameters: {', '.join(missing)}"],
                    ),
                    "byKey": cast(JSONValue, by_key),
                },
            }
        }

    return {
        "validation": {
            "isValid": True,
            "normalizedContextValues": normalized_context,
            "errors": {"general": [], "byKey": {}},
        }
    }


def _normalize_param_value(value: object) -> str:
    """Normalize a parameter value to a string representation.

    :param value: Raw parameter value.
    :returns: String representation for WDK.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ",".join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return str(value)
    return str(value)


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


def _unwrap_search_data(details: JSONObject | None) -> JSONObject | None:
    """Normalize WDK/discovery payload shape to the dict that contains parameters.

    :param details: Search details from WDK/discovery.
    :returns: Search data dict or None.
    """
    if not isinstance(details, dict):
        return None
    search_data_raw = details.get("searchData")
    if isinstance(search_data_raw, dict):
        return search_data_raw
    return details


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
    except Exception:
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
    except WDKError as exc:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_search_details_with_params(
                record_type,
                search_name,
                context_values,
            )
        raise exc


def _extract_param_names(details: JSONObject) -> set[str]:
    """Extract parameter names from WDK search details.

    :param details: Search details from WDK.
    :returns: Set of parameter names.
    """
    if not isinstance(details, dict):
        return set()
    search_data = details.get("searchData")
    if isinstance(search_data, dict):
        params = search_data.get("parameters")
        if isinstance(params, list):
            result: set[str] = set()
            for p in params:
                if not isinstance(p, dict):
                    continue
                name_raw = p.get("name")
                if isinstance(name_raw, str):
                    result.add(name_raw)
            return result
    params = details.get("parameters")
    if isinstance(params, dict):
        return {k for k in params if k}
    if isinstance(params, list):
        result2: set[str] = set()
        for p in params:
            if not isinstance(p, dict):
                continue
            name_raw = p.get("name")
            if isinstance(name_raw, str):
                result2.add(name_raw)
        return result2
    return set()
