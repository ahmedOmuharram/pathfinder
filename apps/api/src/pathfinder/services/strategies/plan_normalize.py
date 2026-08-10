"""Strategy plan normalization helpers.

Produce canonicalized typed parameter values for frontend consumption.
Multi-pick values are vocab-matched + leaf-enforced, ranges are
normalized, scalars are bounds-checked — all expressed as the typed
``ParamValue`` discriminated union.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping

from pathfinder.domain.parameters.canonicalize import ParameterCanonicalizer
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.search_context import (
    get_search_params_under_context,
)
from pathfinder.integrations.veupathdb.value_decoding import encode_params
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search
from pathfinder.services.wdk import get_strategy_api

LoadSearchDetails = Callable[
    [str, str, Mapping[str, ParamValue]],
    Awaitable[WDKSearchResponse],
]
"""Callback that loads WDK search details for a (record_type, search_name)
pair, returning a fully validated ``WDKSearchResponse``."""


async def make_search_detail_loader(site_id: str) -> LoadSearchDetails:
    """Create a search detail loader for a site.

    SSOT for loading WDK search details with parameter context.
    Tries context-dependent details first, falls back to plain GET
    when WDK rejects the context.
    """
    api = get_strategy_api(site_id)

    async def _load(
        record_type: str,
        name: str,
        params: Mapping[str, ParamValue],
    ) -> WDKSearchResponse:
        return await get_search_params_under_context(
            api.client, record_type, name, encode_params(dict(params))
        )

    return _load


def _strip_combine_bq_keys(params: dict[str, ParamValue]) -> None:
    """Remove WDK boolean-question parameter keys from a combine node's params dict."""
    for k in list(params.keys()):
        key = str(k)
        if key == "bq_operator" or key.startswith(("bq_left_op", "bq_right_op")):
            params.pop(k, None)


async def _load_and_cache_spec(
    specs_cache: dict[tuple[str, str, str], dict[str, ParamSpecNormalized]],
    load_search_details: LoadSearchDetails,
    record_type: str,
    name: str,
    site_id: str,
    params: dict[str, ParamValue],
) -> dict[str, ParamSpecNormalized]:
    """Load search spec into cache if not already present, then return it."""
    encoded = encode_params(params)
    ctx_raw = json.dumps(encoded, sort_keys=True, default=str)
    ctx_hash = hashlib.sha256(ctx_raw.encode("utf-8")).hexdigest()
    cache_key = (record_type, name, ctx_hash)
    cached = specs_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        response = await load_search_details(record_type, name, params)
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


async def canonicalize_strategy_ast_parameters(
    *,
    strategy_ast: StrategyAst,
    site_id: str,
    load_search_details: LoadSearchDetails | None = None,
) -> StrategyAst:
    """Canonicalize all search/transform node parameters using WDK specs.

    ``load_search_details(record_type, name, params)`` must return a validated
    ``WDKSearchResponse``.  When omitted a default loader is created via
    :func:`make_search_detail_loader`.
    """
    if load_search_details is None:
        load_search_details = await make_search_detail_loader(site_id)
    record_type = strategy_ast.record_type

    # NOTE: search details can be context-dependent (dependent vocabularies).
    # Cache by (record_type, search_name, context_hash) to avoid incorrect reuse.
    specs_cache: dict[tuple[str, str, str], dict[str, ParamSpecNormalized]] = {}

    async def canonicalize_node(node: StrategyStepNode) -> None:
        name = node.search_name
        params: dict[str, ParamValue] = dict(node.parameters)

        is_combine = (
            node.primary_input is not None and node.secondary_input is not None
        ) or node.search_name == COMBINE_SEARCH_NAME

        if is_combine:
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

    await canonicalize_node(strategy_ast.root)
    return strategy_ast
