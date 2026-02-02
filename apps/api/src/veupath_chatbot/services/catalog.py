"""Catalog services: sites, record types, searches, parameter metadata.

Single source of truth for catalog/discovery logic used by both:
- HTTP transport (`transport/http/routers/sites.py`)
- AI tools (`ai/tools/catalog_tools.py`)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
    find_input_step_param,
)
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.platform.errors import ErrorCode, ValidationError as CoreValidationError
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import (
    get_wdk_client,
    list_sites as list_wdk_sites,
)

logger = logging.getLogger(__name__)


async def list_sites() -> list[dict[str, Any]]:
    return [site.to_dict() for site in list_wdk_sites()]


async def get_record_types(site_id: str) -> list[dict[str, Any]]:
    discovery = get_discovery_service()
    record_types = await discovery.get_record_types(site_id)
    return [
        {
            "name": rt.get("urlSegment", rt.get("name")),
            "displayName": rt.get("displayName"),
            "description": rt.get("description", ""),
        }
        for rt in record_types
    ]


async def list_searches(site_id: str, record_type: str) -> list[dict[str, str]]:
    discovery = get_discovery_service()
    searches = await discovery.get_searches(site_id, record_type)
    return [
        {
            "name": s.get("urlSegment", s.get("name", "")),
            "displayName": s.get("displayName", ""),
            "description": s.get("description", ""),
        }
        for s in searches
        if not s.get("isInternal", False)
    ]


async def get_search_parameters(
    site_id: str,
    record_type: str,
    search_name: str,
) -> dict[str, Any]:
    """Get detailed parameter info for a specific search.

    This is intentionally defensive: WDK responses can vary by site/endpoint.
    """
    discovery = get_discovery_service()
    details: dict[str, Any] | None = None
    resolved_record_type = record_type

    record_types = await discovery.get_record_types(site_id)

    def normalize(value: str) -> str:
        return value.strip().lower()

    if record_type:
        normalized = normalize(record_type)
        exact = [
            rt
            for rt in record_types
            if normalize(rt.get("urlSegment", rt.get("name", ""))) == normalized
        ]
        if exact:
            resolved_record_type = exact[0].get(
                "urlSegment", exact[0].get("name", resolved_record_type)
            )
        else:
            display_matches = [
                rt for rt in record_types if normalize(rt.get("displayName", "")) == normalized
            ]
            if len(display_matches) == 1:
                resolved_record_type = display_matches[0].get(
                    "urlSegment", display_matches[0].get("name", resolved_record_type)
                )

    try:
        details = await discovery.get_search_details(
            site_id, resolved_record_type, search_name, expand_params=True
        )
    except Exception as e:
        for rt in record_types:
            rt_name = rt.get("urlSegment", rt.get("name", ""))
            if not rt_name:
                continue
            searches = await discovery.get_searches(site_id, rt_name)
            match = next(
                (
                    s
                    for s in searches
                    if s.get("urlSegment") == search_name or s.get("name") == search_name
                ),
                None,
            )
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
            available_searches = [
                s.get("urlSegment", s.get("name", "")) for s in available
            ]
            raise CoreValidationError(
                title="Search not found",
                detail=f"Search not found: {search_name}",
                errors=[
                    {
                        "path": "searchName",
                        "message": f"Search not found: {search_name}",
                        "code": ErrorCode.SEARCH_NOT_FOUND.value,
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "availableSearches": available_searches,
                        "details": str(e),
                    }
                ],
            )

    if isinstance(details.get("searchData"), dict):
        details = details["searchData"]

    param_specs = extract_param_specs(details if isinstance(details, dict) else {})

    def _allowed_values(vocab: dict[str, Any] | list[Any] | None) -> list[str]:
        if not vocab:
            return []
        values: list[str] = []
        seen: set[str] = set()
        for entry in flatten_vocab(vocab, prefer_term=False):
            candidate = entry.get("display") or entry.get("value")
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

    param_info: list[dict[str, Any]] = []
    for spec in param_specs:
        name = spec.get("name") or spec.get("paramName") or spec.get("id") or ""
        if not name:
            continue
        if "isRequired" in spec:
            required = bool(spec.get("isRequired"))
        else:
            required = not spec.get("allowEmptyValue", False)
        info: dict[str, Any] = {
            "name": str(name),
            "displayName": spec.get("displayName", str(name)),
            "type": spec.get("type", "string"),
            "required": required,
            "help": spec.get("help", ""),
        }

        allowed = _allowed_values(spec.get("vocabulary"))
        if allowed:
            info["allowedValues"] = allowed

        if spec.get("initialDisplayValue"):
            info["defaultValue"] = spec["initialDisplayValue"]
        if spec.get("defaultValue") is not None and "defaultValue" not in info:
            info["defaultValue"] = spec.get("defaultValue")

        param_info.append(info)

    return {
        "searchName": search_name,
        "displayName": details.get("displayName", search_name),
        "description": details.get("description", ""),
        "parameters": param_info,
        "resolvedRecordType": resolved_record_type,
    }


async def get_search_parameters_tool(
    site_id: str,
    record_type: str,
    search_name: str,
) -> dict[str, Any]:
    """Tool-friendly wrapper that returns standardized tool_error payloads."""
    try:
        return await get_search_parameters(site_id, record_type, search_name)
    except CoreValidationError as exc:
        code = None
        if exc.errors and isinstance(exc.errors, list):
            code = exc.errors[0].get("code")
        return tool_error(
            code or ErrorCode.VALIDATION_ERROR,
            exc.detail or exc.title,
            errors=exc.errors,
        )


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
) -> list[dict[str, str]]:
    """Find searches matching a query term (name/description and sometimes detail text)."""
    discovery = get_discovery_service()
    record_types: list[str] = []
    if isinstance(record_type, list):
        record_types = [str(rt) for rt in record_type if rt]
    elif isinstance(record_type, str) and record_type:
        record_types = [record_type]
    record_types = list(dict.fromkeys(record_types))

    raw_terms = re.findall(r"[A-Za-z0-9]+", query or "")
    terms = [t.lower() for t in raw_terms if t]
    query_lower = query.lower() if query else ""
    matches: list[dict[str, Any]] = []

    def add_matches(searches: list[dict[str, Any]], rt_name: str) -> None:
        for search in searches:
            if search.get("isInternal", False):
                continue
            name = search.get("displayName", "") or search.get("urlSegment", "")
            desc = search.get("description", "")
            haystack = f"{name} {desc}".lower()
            score = 0
            if terms:
                score = sum(1 for term in terms if term in haystack)
            else:
                if query_lower and (query_lower in name.lower() or query_lower in desc.lower()):
                    score = 1
            if score > 0:
                matches.append(
                    {
                        "name": search.get("urlSegment", search.get("name", "")),
                        "displayName": name,
                        "description": desc,
                        "recordType": rt_name,
                        "score": str(score),
                    }
                )

    for rt_name in record_types:
        searches = await discovery.get_searches(site_id, rt_name)
        add_matches(searches, rt_name)

    matches.sort(key=lambda item: (-int(item.get("score", "0")), item["displayName"]))
    for item in matches:
        item.pop("score", None)
    return matches[:20]


async def expand_search_details_with_params(
    site_id: str,
    record_type: str,
    search_name: str,
    context_values: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return WDK search details after applying (WDK-wire) context values.

    NOTE: despite the historical name, this is *not* a pure validation API; it returns
    WDK search details payload. Keep it separate from the public validation endpoint.
    """
    client = get_wdk_client(site_id)
    raw_context = context_values or {}
    normalized_context: dict[str, Any] = {}
    details: dict[str, Any] | None = None
    allowed: set[str] = set()
    try:
        discovery = get_discovery_service()
        details = await discovery.get_search_details(
            site_id, record_type, search_name, expand_params=True
        )
        allowed = _extract_param_names(details)
    except Exception:
        details = None
        allowed = set()

    filtered_context = (
        {key: value for key, value in raw_context.items() if key in allowed}
        if allowed
        else dict(raw_context)
    )

    if details:
        if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
            details = details["searchData"]
        specs = adapt_param_specs(details if isinstance(details, dict) else {})
    else:
        specs = {}

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
            if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
                details = details["searchData"]
            specs = adapt_param_specs(details if isinstance(details, dict) else {})
            normalizer = ParameterNormalizer(specs)
            normalized_context = normalizer.normalize(filtered_context)
        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized_context[input_step_param] = ""
    else:
        normalized_context = {
            key: _normalize_param_value(value) for key, value in filtered_context.items()
        }
    resolved_record_type = await _resolve_record_type_for_search(
        client, record_type, search_name
    )
    try:
        return await client.get_search_details_with_params(
            resolved_record_type,
            search_name,
            normalized_context,
        )
    except WDKError as exc:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_search_details_with_params(
                resolved_record_type,
                search_name,
                normalized_context,
            )
        raise exc


async def validate_search_params(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    context_values: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and canonicalize search parameters for UI consumption.

    Returns a stable payload:
      { "validation": { "isValid": bool, "normalizedContextValues": {...}, "errors": {...} } }

    The goal is to keep the frontend a consumer of backend normalization + validation,
    without requiring the UI to interpret raw WDK payloads.
    """
    from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
    from veupath_chatbot.domain.parameters.specs import adapt_param_specs, extract_param_specs
    from veupath_chatbot.platform.errors import ValidationError as AppValidationError

    raw_context = context_values or {}
    normalized_context: dict[str, Any] = {}
    details: dict[str, Any] | None = None
    allowed: set[str] = set()
    discovery = get_discovery_service()
    try:
        details = await discovery.get_search_details(
            site_id, record_type, search_name, expand_params=True
        )
        allowed = _extract_param_names(details)
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

    filtered_context = (
        {key: value for key, value in raw_context.items() if key in allowed}
        if allowed
        else dict(raw_context)
    )

    if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
        details = details["searchData"]
    spec_payload = details if isinstance(details, dict) else {}
    spec_map = adapt_param_specs(spec_payload)
    raw_specs = extract_param_specs(spec_payload)

    try:
        canonicalizer = ParameterCanonicalizer(spec_map)
        normalized_context = canonicalizer.canonicalize(filtered_context)
    except AppValidationError as exc:
        by_key: dict[str, list[str]] = {}
        general: list[str] = []
        for err in (exc.errors or []) or []:
            param = err.get("param") or err.get("path")
            message = err.get("message") or err.get("detail") or exc.detail or exc.title
            if param:
                by_key.setdefault(str(param), []).append(str(message))
            else:
                general.append(str(message))
        if not general:
            general = [exc.detail or exc.title]
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": {},
                "errors": {"general": general, "byKey": by_key},
            }
        }

    # Required checks using raw WDK specs (keeps semantics aligned with WDK).
    required_specs = [
        p for p in raw_specs if p.get("isRequired", False) or not p.get("allowEmptyValue", True)
    ]
    missing: list[str] = []
    for spec in required_specs:
        name = spec.get("name")
        if not name:
            continue
        if name not in normalized_context:
            missing.append(str(name))
            continue
        value = normalized_context.get(str(name))
        param_type = (spec.get("type") or "").lower()
        if param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]") or (isinstance(value, list) and len(value) == 0):
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
                    "general": [f"Missing required parameters: {', '.join(missing)}"],
                    "byKey": by_key,
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


def _extract_param_names(details: dict[str, Any]) -> set[str]:
    if not isinstance(details, dict):
        return set()
    search_data = details.get("searchData")
    if isinstance(search_data, dict):
        params = search_data.get("parameters")
        if isinstance(params, list):
            return {
                p.get("name")
                for p in params
                if isinstance(p, dict) and p.get("name")
            }
    params = details.get("parameters")
    if isinstance(params, dict):
        return {k for k in params.keys() if k}
    if isinstance(params, list):
        return {p.get("name") for p in params if isinstance(p, dict) and p.get("name")}
    return set()


async def _resolve_record_type_for_search(
    client: VEuPathDBClient, record_type: str, search_name: str
) -> str:
    """Resolve which record type actually contains a search name."""
    try:
        record_types = await client.get_record_types()
    except Exception:
        return record_type
    ordered: list[str] = []
    for rt in record_types:
        if isinstance(rt, str):
            rt_name = rt
        else:
            rt_name = rt.get("urlSegment") or rt.get("name")
        if not rt_name:
            continue
        if rt_name == record_type:
            ordered.insert(0, rt_name)
        else:
            ordered.append(rt_name)
    for rt_name in ordered:
        try:
            searches = await client.get_searches(rt_name)
        except Exception:
            continue
        if any(
            search.get("urlSegment") == search_name or search.get("name") == search_name
            for search in searches
        ):
            return rt_name
    return record_type

