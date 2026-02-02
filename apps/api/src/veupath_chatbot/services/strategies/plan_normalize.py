"""Strategy plan normalization helpers.

This module provides two distinct concepts:

1) Canonicalization (API-facing):
   - Produce canonical JSON shapes so the frontend is a consumer:
     multi-pick -> list[str], ranges -> {min,max}, etc.

2) WDK wire normalization (integration-facing, deprecated):
   - Older code joined lists into CSV strings, which is lossy and should not be used
     for persisted plans. Kept temporarily for compatibility where needed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.platform.errors import ValidationError


async def canonicalize_plan_parameters(
    *,
    plan: dict[str, Any],
    site_id: str,
    load_search_details: Any,
) -> dict[str, Any]:
    """Canonicalize all search/transform node parameters using WDK specs.

    `load_search_details(record_type, search_or_transform_name) -> dict` must return a WDK
    payload with expanded params (or raise).
    """
    root = plan.get("root")
    if not isinstance(root, dict):
        return plan
    record_type = plan.get("recordType")
    if not isinstance(record_type, str) or not record_type:
        raise ValidationError(
            title="Invalid plan",
            detail="Plan is missing 'recordType'.",
            errors=[{"path": "recordType", "message": "Required", "code": "INVALID_STRATEGY"}],
        )

    # NOTE: search details can be context-dependent (dependent vocabularies).
    # Cache by (record_type, search_name, context_hash) to avoid incorrect reuse.
    specs_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def canonicalize_node(node: dict[str, Any]) -> dict[str, Any]:
        node_type = node.get("type")
        if node_type in {"search", "transform"}:
            name = node.get("searchName") if node_type == "search" else node.get("transformName")
            if not isinstance(name, str) or not name:
                raise ValidationError(
                    title="Invalid plan",
                    detail=f"Missing {('searchName' if node_type == 'search' else 'transformName')}.",
                    errors=[
                        {
                            "path": "root",
                            "message": "Missing step name",
                            "code": "INVALID_STRATEGY",
                        }
                    ],
                )
            params = node.get("parameters")
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise ValidationError(
                    title="Invalid plan",
                    detail="Step parameters must be an object.",
                    errors=[{"path": "parameters", "message": "Expected object"}],
                )

            ctx_raw = json.dumps(params, sort_keys=True, default=str)
            ctx_hash = hashlib.sha1(ctx_raw.encode("utf-8")).hexdigest()

            cache_key = (record_type, name, ctx_hash)
            details = specs_cache.get(cache_key)
            if details is None:
                try:
                    details = await load_search_details(record_type, name, params)
                except Exception as exc:
                    raise ValidationError(
                        title="Failed to load search metadata",
                        detail=f"Unable to load parameter metadata for '{name}' ({record_type}).",
                        errors=[
                            {"searchName": name, "recordType": record_type, "siteId": site_id}
                        ],
                    ) from exc
                if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
                    details = details["searchData"]
                specs_cache[cache_key] = details if isinstance(details, dict) else {}
            spec_map = adapt_param_specs(details if isinstance(details, dict) else {})
            canonicalizer = ParameterCanonicalizer(spec_map)
            node["parameters"] = canonicalizer.canonicalize(params)

        if node_type == "combine":
            left = node.get("left")
            right = node.get("right")
            if isinstance(left, dict):
                await canonicalize_node(left)
            if isinstance(right, dict):
                await canonicalize_node(right)
        if node_type == "transform":
            input_node = node.get("input")
            if isinstance(input_node, dict):
                await canonicalize_node(input_node)
        return node

    await canonicalize_node(root)
    plan["root"] = root
    return plan


def _normalize_param_value_to_wdk_string(value: Any) -> str:
    """Deprecated: lossy WDK coercion (kept temporarily)."""
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


def _normalize_plan_parameters_to_wdk_strings(plan: dict[str, Any]) -> dict[str, Any]:
    """Deprecated: ensure all search/transform parameters are WDK-safe strings."""
    root = plan.get("root")
    if not isinstance(root, dict):
        return plan

    def normalize_node(node: dict[str, Any]) -> dict[str, Any]:
        node_type = node.get("type")
        if node_type in {"search", "transform"}:
            params = node.get("parameters")
            if isinstance(params, dict):
                node["parameters"] = {
                    key: _normalize_param_value_to_wdk_string(value)
                    for key, value in params.items()
                }
        if node_type == "combine":
            left = node.get("left")
            right = node.get("right")
            if isinstance(left, dict):
                normalize_node(left)
            if isinstance(right, dict):
                normalize_node(right)
        if node_type == "transform":
            input_node = node.get("input")
            if isinstance(input_node, dict):
                normalize_node(input_node)
        return node

    normalize_node(root)
    plan["root"] = root
    return plan

