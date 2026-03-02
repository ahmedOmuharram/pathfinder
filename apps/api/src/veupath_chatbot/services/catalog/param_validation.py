"""Validation of search parameter values."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONObject, JSONValue

from .param_resolution import (
    _extract_param_names,
    _filter_context_values,
    _unwrap_search_data,
    expand_search_details_with_params,
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
