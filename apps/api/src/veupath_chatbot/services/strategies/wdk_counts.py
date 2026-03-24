"""Step count computation: get per-step result counts from WDK.

Supports two paths:
- **Leaf-only strategies**: parallel anonymous reports (fast, no strategy creation)
- **Complex strategies**: temporary WDK strategy via step creation

Results are cached by plan hash to avoid redundant API calls.
"""

import asyncio
import hashlib
import json

from cachetools import LRUCache

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    walk_step_tree,
)
from veupath_chatbot.domain.strategy.ops import get_wdk_operator
from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
)
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.strategies.sync import build_step_tree_from_graph
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload

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
    parameters: dict[str, str],
) -> int | None:
    """Get result count for a single search using the anonymous report endpoint.

    ``POST /record-types/{recordType}/searches/{searchName}/reports/standard``
    with ``numRecords: 0`` returns only ``meta.totalCount`` -- no step or
    strategy creation needed. Returns ``None`` on failure.
    """
    config = WDKSearchConfig(parameters=parameters)
    report_config: JSONObject = {"pagination": {"offset": 0, "numRecords": 0}}
    try:
        answer = await client.run_search_report(
            record_type, search_name, config, report_config
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


def is_leaf_only_plan(root: PlanStepNode) -> bool:
    """Check if all steps in the plan tree are leaf (search) steps."""
    return all(step.infer_kind() == "search" for step in walk_step_tree(root))


async def compute_step_counts_for_plan(
    plan: JSONObject,
    payload: StrategyPlanPayload,
    site_id: str,
) -> dict[str, int | None]:
    """Compute per-step result counts for a strategy plan.

    For **leaf-only strategies** (all search steps, no combines/transforms),
    uses WDK's anonymous report endpoint in parallel -- no step or strategy
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
    if is_leaf_only_plan(payload.root):
        counts = await _compute_leaf_counts_parallel(
            api.client, payload.root, payload.record_type
        )
        _cache_counts(cache_key, counts)
        return counts

    # Slow path: complex strategies require creating steps + temporary strategy.
    counts = await _compute_counts_via_temp_strategy(api, payload, site_id)
    _cache_counts(cache_key, counts)
    return counts


async def _compute_leaf_counts_parallel(
    client: VEuPathDBClient,
    root: PlanStepNode,
    record_type: str,
) -> dict[str, int | None]:
    """Compute counts for all leaf steps in parallel using anonymous reports."""
    all_steps = walk_step_tree(root)

    tasks = [
        _count_via_anonymous_report(
            client,
            record_type,
            step.search_name,
            step.wdk_parameters,
        )
        for step in all_steps
    ]
    results = await asyncio.gather(*tasks)
    return {step.id: count for step, count in zip(all_steps, results, strict=True)}


async def _create_wdk_step(
    api: StrategyAPI,
    step: PlanStepNode,
    record_type: str,
    wdk_step_ids: dict[str, int],
) -> int | None:
    """Create a single WDK step and return its WDK ID, or None on failure."""
    kind = step.infer_kind()
    params = step.wdk_parameters
    try:
        if kind == "search":
            result = await api.create_step(
                NewStepSpec(
                    search_name=step.search_name,
                    search_config=WDKSearchConfig(parameters=params),
                ),
                record_type=record_type,
            )
            return result.id
        if kind == "transform" and step.primary_input:
            input_wdk_id = wdk_step_ids.get(step.primary_input.id)
            if input_wdk_id is None:
                return None
            result = await api.create_transform_step(
                NewStepSpec(
                    search_name=step.search_name,
                    search_config=WDKSearchConfig(parameters=params),
                ),
                input_step_id=input_wdk_id,
                record_type=record_type,
            )
            return result.id
        if kind == "combine" and step.primary_input and step.secondary_input:
            primary_wdk_id = wdk_step_ids.get(step.primary_input.id)
            secondary_wdk_id = wdk_step_ids.get(step.secondary_input.id)
            if primary_wdk_id is None or secondary_wdk_id is None:
                return None
            operator = get_wdk_operator(step.operator) if step.operator else "INTERSECT"
            result = await api.create_combined_step(
                primary_step_id=primary_wdk_id,
                secondary_step_id=secondary_wdk_id,
                boolean_operator=operator,
                record_type=record_type,
            )
            return result.id
    except AppError as exc:
        logger.warning(
            "Failed to create step for count computation",
            step_id=step.id,
            error=str(exc),
        )
    return None


async def _read_counts_from_strategy(
    api: StrategyAPI,
    strategy_id: int,
    all_steps: list[PlanStepNode],
    wdk_step_ids: dict[str, int],
    counts: dict[str, int | None],
) -> None:
    """Read estimatedSize from a WDK strategy and populate the counts dict."""
    try:
        wdk_strategy = await api.get_strategy(strategy_id)
        for step in all_steps:
            wdk_id = wdk_step_ids.get(step.id)
            if wdk_id is None:
                continue
            wdk_step = wdk_strategy.steps.get(str(wdk_id))
            if wdk_step is not None and wdk_step.estimated_size is not None:
                counts[step.id] = wdk_step.estimated_size
    except AppError as e:
        logger.warning("Failed to read counts from strategy payload", error=str(e))


async def _compute_counts_via_temp_strategy(
    api: StrategyAPI,
    payload: StrategyPlanPayload,
    site_id: str,
) -> dict[str, int | None]:
    """Compute counts by creating steps, a temporary strategy, and reading counts.

    Creates each step on WDK, builds a step tree, creates a temporary
    strategy, reads counts from the strategy payload, then cleans up.
    """
    all_steps = walk_step_tree(payload.root)

    # Create each step on WDK and collect local->WDK ID mapping.
    wdk_step_ids: dict[str, int] = {}
    for step in all_steps:
        wdk_id = await _create_wdk_step(api, step, payload.record_type, wdk_step_ids)
        if wdk_id is not None:
            wdk_step_ids[step.id] = wdk_id

    counts: dict[str, int | None] = {step.id: None for step in all_steps}

    # If we couldn't create all steps, return None counts.
    if len(wdk_step_ids) != len(all_steps):
        return counts

    # Build step tree and create temporary strategy.
    try:
        step_tree = build_step_tree_from_graph(payload.root, wdk_step_ids)
    except AppError:
        return counts

    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=step_tree,
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
            step_count=len(all_steps),
        )

    if temp_strategy_id is not None:
        await _read_counts_from_strategy(
            api, temp_strategy_id, all_steps, wdk_step_ids, counts
        )

    await delete_temp_strategy(api, temp_strategy_id)
    return counts


def _cache_counts(cache_key: str, counts: dict[str, int | None]) -> None:
    """Store counts in the LRU cache."""
    _STEP_COUNTS_CACHE[cache_key] = counts
