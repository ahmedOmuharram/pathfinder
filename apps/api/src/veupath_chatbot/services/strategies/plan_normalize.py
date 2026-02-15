"""Strategy plan normalization helpers.

Produce canonical JSON shapes for frontend consumption. Multi-pick becomes
list[str], ranges become ``{min, max}``, etc.
"""

from __future__ import annotations

import collections.abc
import hashlib
import json
from collections.abc import Callable, Mapping

from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue


async def canonicalize_plan_parameters(
    *,
    plan: JSONObject,
    site_id: str,
    load_search_details: Callable[
        [str, str, Mapping[str, JSONValue]], collections.abc.Awaitable[JSONObject]
    ],
) -> JSONObject:
    """Canonicalize all search/transform node parameters using WDK specs.

    `load_search_details(record_type, search_or_transform_name, params) -> dict` must return a WDK
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
            errors=[
                {
                    "path": "recordType",
                    "message": "Required",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    # NOTE: search details can be context-dependent (dependent vocabularies).
    # Cache by (record_type, search_name, context_hash) to avoid incorrect reuse.
    specs_cache: dict[tuple[str, str, str], JSONObject] = {}

    async def canonicalize_node(node: JSONObject) -> JSONObject:
        name = node.get("searchName")
        if not isinstance(name, str) or not name:
            raise ValidationError(
                title="Invalid plan",
                detail="Missing searchName.",
                errors=[
                    {
                        "path": "root",
                        "message": "Missing step searchName",
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

        primary = node.get("primaryInput")
        secondary = node.get("secondaryInput")
        is_combine = isinstance(primary, dict) and isinstance(secondary, dict)

        # Combine nodes are structural (primary+secondary+operator) and do not require
        # WDK parameter metadata. Some WDK deployments do not expose a corresponding
        # `boolean_question_*` search for every record type, so attempting to load
        # metadata here can incorrectly fail normalization.
        if is_combine:
            # Defensive cleanup: if a caller encoded a combine using WDK boolean-question
            # parameter conventions, strip those keys from persisted plans.
            for k in list(params.keys()):
                key = str(k)
                if (
                    key == "bq_operator"
                    or key.startswith("bq_left_op")
                    or key.startswith("bq_right_op")
                ):
                    params.pop(k, None)
            node["parameters"] = params

            if isinstance(primary, dict):
                await canonicalize_node(primary)
            if isinstance(secondary, dict):
                await canonicalize_node(secondary)
            return node

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
                        {
                            "searchName": name,
                            "recordType": record_type,
                            "siteId": site_id,
                        }
                    ],
                ) from exc
            if isinstance(details, dict):
                search_data = details.get("searchData")
                if isinstance(search_data, dict):
                    details = search_data
            specs_cache[cache_key] = details if isinstance(details, dict) else {}
        spec_map = adapt_param_specs(details if isinstance(details, dict) else {})
        canonicalizer = ParameterCanonicalizer(spec_map)
        node["parameters"] = canonicalizer.canonicalize(params)

        if isinstance(primary, dict):
            await canonicalize_node(primary)
        if isinstance(secondary, dict):
            await canonicalize_node(secondary)
        return node

    await canonicalize_node(root)
    plan["root"] = root
    return plan
