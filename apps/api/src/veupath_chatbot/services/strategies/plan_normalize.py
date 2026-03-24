"""Strategy plan normalization helpers.

Produce canonical JSON shapes for frontend consumption. Multi-pick becomes
list[str], ranges become ``{min, max}``, etc.
"""

import collections.abc
import hashlib
import json
from collections.abc import Callable, Mapping

from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    adapt_param_specs_from_search,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue

from .schemas import StrategyPlanPayload


def _strip_combine_bq_keys(params: JSONObject) -> None:
    """Remove WDK boolean-question parameter keys from a combine node's params dict."""
    for k in list(params.keys()):
        key = str(k)
        if key == "bq_operator" or key.startswith(("bq_left_op", "bq_right_op")):
            params.pop(k, None)


async def _load_and_cache_spec(
    specs_cache: dict[tuple[str, str, str], dict[str, ParamSpecNormalized]],
    load_search_details: Callable[
        [str, str, Mapping[str, JSONValue]], collections.abc.Awaitable[JSONObject]
    ],
    record_type: str,
    name: str,
    site_id: str,
    params: JSONObject,
) -> dict[str, ParamSpecNormalized]:
    """Load search spec into cache if not already present, then return it."""
    ctx_raw = json.dumps(params, sort_keys=True, default=str)
    ctx_hash = hashlib.sha256(ctx_raw.encode("utf-8")).hexdigest()
    cache_key = (record_type, name, ctx_hash)
    cached = specs_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        details = await load_search_details(record_type, name, params)
        response = WDKSearchResponse.model_validate(details)
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
    spec_map = adapt_param_specs_from_search(response.search_data)
    specs_cache[cache_key] = spec_map
    return spec_map


async def canonicalize_plan_parameters(
    *,
    plan: StrategyPlanPayload,
    site_id: str,
    load_search_details: Callable[
        [str, str, Mapping[str, JSONValue]], collections.abc.Awaitable[JSONObject]
    ],
) -> StrategyPlanPayload:
    """Canonicalize all search/transform node parameters using WDK specs.

    `load_search_details(record_type, search_or_transform_name, params) -> dict` must return a WDK
    payload with expanded params (or raise).
    """
    record_type = plan.record_type

    # NOTE: search details can be context-dependent (dependent vocabularies).
    # Cache by (record_type, search_name, context_hash) to avoid incorrect reuse.
    specs_cache: dict[tuple[str, str, str], dict[str, ParamSpecNormalized]] = {}

    async def canonicalize_node(node: PlanStepNode) -> None:
        name = node.search_name
        params = dict(node.parameters)

        is_combine = node.primary_input is not None and node.secondary_input is not None

        # Combine nodes are structural (primary+secondary+operator) and do not require
        # WDK parameter metadata. Some WDK deployments do not expose a corresponding
        # `boolean_question_*` search for every record type, so attempting to load
        # metadata here can incorrectly fail normalization.
        if is_combine:
            # Defensive cleanup: if a caller encoded a combine using WDK boolean-question
            # parameter conventions, strip those keys from persisted plans.
            _strip_combine_bq_keys(params)
            node.parameters = params
        else:
            spec_map = await _load_and_cache_spec(
                specs_cache, load_search_details, record_type, name, site_id, params
            )
            canonicalizer = ParameterCanonicalizer(spec_map)
            node.parameters = canonicalizer.canonicalize(params)

        if node.primary_input is not None:
            await canonicalize_node(node.primary_input)
        if node.secondary_input is not None:
            await canonicalize_node(node.secondary_input)

    await canonicalize_node(plan.root)
    return plan
