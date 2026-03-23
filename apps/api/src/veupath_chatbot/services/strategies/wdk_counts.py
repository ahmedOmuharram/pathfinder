"""Step count computation: get per-step result counts from WDK.

Supports two paths:
- **Leaf-only strategies**: parallel anonymous reports (fast, no strategy creation)
- **Complex strategies**: temporary WDK strategy compilation (slower)

Results are cached by plan hash to avoid redundant API calls.
"""

import asyncio
import hashlib
import json

from cachetools import LRUCache

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_helpers import delete_temp_strategy

logger = get_logger(__name__)

_STEP_COUNTS_CACHE: LRUCache[str, dict[str, int | None]] = LRUCache(maxsize=20)


def plan_cache_key(site_id: str, plan: JSONObject) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{site_id}:{digest}"


async def _count_via_anonymous_report(
    client: VEuPathDBClient,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
) -> int | None:
    """Get result count for a single search using the anonymous report endpoint.

    ``POST /record-types/{recordType}/searches/{searchName}/reports/standard``
    with ``numRecords: 0`` returns only ``meta.totalCount`` — no step or
    strategy creation needed. Returns ``None`` on failure.
    """
    search_config: JSONObject = {"parameters": parameters}
    report_config: JSONObject = {"pagination": {"offset": 0, "numRecords": 0}}
    try:
        answer = await client.run_search_report(
            record_type, search_name, search_config, report_config
        )
    except AppError as e:
        logger.warning(
            "Anonymous report count failed",
            record_type=record_type,
            search_name=search_name,
            error=str(e),
        )
        return None
    else:
        return answer.meta.total_count


def is_leaf_only_strategy(strategy_ast: StrategyAST) -> bool:
    """Check if all steps in the strategy are leaf (search) steps."""
    return all(step.infer_kind() == "search" for step in strategy_ast.get_all_steps())


async def compute_step_counts_for_plan(
    plan: JSONObject,
    strategy_ast: StrategyAST,
    site_id: str,
) -> dict[str, int | None]:
    """Compute per-step result counts for a strategy plan.

    For **leaf-only strategies** (all search steps, no combines/transforms),
    uses WDK's anonymous report endpoint in parallel — no step or strategy
    creation needed. This is dramatically faster than full compilation.

    For **complex strategies** (with combines/transforms), falls back to
    creating a temporary WDK strategy to get server-computed counts.

    Results are cached by plan hash.
    """
    cache_key = plan_cache_key(site_id, plan)
    cached: dict[str, int | None] | None = _STEP_COUNTS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    api = get_strategy_api(site_id)

    # Fast path: leaf-only strategies use parallel anonymous reports.
    if is_leaf_only_strategy(strategy_ast):
        counts = await _compute_leaf_counts_parallel(api.client, strategy_ast)
        _cache_counts(cache_key, counts)
        return counts

    # Slow path: complex strategies require full WDK compilation.
    counts = await _compute_counts_via_compilation(api, strategy_ast, site_id)
    _cache_counts(cache_key, counts)
    return counts


async def _compute_leaf_counts_parallel(
    client: VEuPathDBClient,
    strategy_ast: StrategyAST,
) -> dict[str, int | None]:
    """Compute counts for all leaf steps in parallel using anonymous reports."""
    all_steps = strategy_ast.get_all_steps()
    record_type = strategy_ast.record_type

    tasks = [
        _count_via_anonymous_report(
            client, record_type, step.search_name, step.parameters or {}
        )
        for step in all_steps
    ]
    results = await asyncio.gather(*tasks)
    return {step.id: count for step, count in zip(all_steps, results, strict=True)}


async def _compute_counts_via_compilation(
    api: StrategyAPI,
    strategy_ast: StrategyAST,
    site_id: str,
) -> dict[str, int | None]:
    """Compute counts by creating a temporary WDK strategy (legacy path)."""
    result = await compile_strategy(
        strategy_ast,
        api,
        site_id=site_id,
        resolve_record_type=True,
    )

    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=result.step_tree,
            name="Pathfinder step counts",
            description=None,
            is_internal=True,
        )
        temp_strategy_id = created.id
    except AppError as exc:
        logger.exception(
            "Failed to create temporary WDK strategy for step counts",
            error=str(exc),
            site_id=site_id,
            step_count=len(result.steps),
        )

    counts: dict[str, int | None] = {step.local_id: None for step in result.steps}

    if temp_strategy_id is not None:
        try:
            wdk_strategy = await api.get_strategy(temp_strategy_id)
            for step in result.steps:
                wdk_step = wdk_strategy.steps.get(str(step.wdk_step_id))
                if wdk_step is not None and wdk_step.estimated_size is not None:
                    counts[step.local_id] = wdk_step.estimated_size
        except AppError as e:
            logger.warning("Failed to read counts from strategy payload", error=str(e))

    await delete_temp_strategy(api, temp_strategy_id)
    return counts


def _cache_counts(cache_key: str, counts: dict[str, int | None]) -> None:
    """Store counts in the LRU cache."""
    _STEP_COUNTS_CACHE[cache_key] = counts
