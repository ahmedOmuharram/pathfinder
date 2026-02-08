"""WDK step counts helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

logger = get_logger(__name__)

_STEP_COUNTS_CACHE: "OrderedDict[str, dict[str, int | None]]" = OrderedDict()
_STEP_COUNTS_CACHE_MAX = 20


def _plan_cache_key(site_id: str, plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{site_id}:{digest}"


async def compute_step_counts_for_plan(
    plan: dict[str, Any],
    strategy_ast: StrategyAST,
    site_id: str,
) -> dict[str, int | None]:
    cache_key = _plan_cache_key(site_id, plan)
    cached = _STEP_COUNTS_CACHE.get(cache_key)
    if cached is not None:
        if any(isinstance(value, int) for value in cached.values()):
            _STEP_COUNTS_CACHE.move_to_end(cache_key)
            return cached

    api = get_strategy_api(site_id)
    result = await compile_strategy(
        strategy_ast,
        api,
        site_id=site_id,
        resolve_record_type=True,
    )

    # WDK step reports (used for counts) require that the step be part of a strategy.
    # The compiler creates steps + a stepTree, but does not persist a WDK strategy.
    # Create a temporary (unsaved) WDK strategy so counts can be computed, then delete it.
    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=result.step_tree,
            name="Pathfinder step counts",
            description=None,
            is_internal=True,
        )
        raw_id = (
            (created or {}).get("id")
            or (created or {}).get("strategyId")
            or (created or {}).get("strategy_id")
        )
        if raw_id is not None:
            try:
                temp_strategy_id = int(raw_id)
            except (TypeError, ValueError):
                temp_strategy_id = None
    except Exception:
        # Best-effort: if we can't create a strategy, counts will likely remain unknown.
        temp_strategy_id = None

    counts: dict[str, int | None] = {step.local_id: None for step in result.steps}

    semaphore = asyncio.Semaphore(8)

    async def fetch_count(step_id: int) -> int | None:
        async with semaphore:
            try:
                return await api.get_step_count(step_id)
            except Exception:
                return None

    tasks = [fetch_count(step.wdk_step_id) for step in result.steps]
    counts_raw = await asyncio.gather(*tasks, return_exceptions=False)
    for step, count in zip(result.steps, counts_raw):
        if isinstance(count, int):
            counts[step.local_id] = count

    # Best-effort cleanup (avoid polluting the user's WDK account).
    if temp_strategy_id is not None:
        try:
            await api.delete_strategy(temp_strategy_id)
        except Exception:
            pass

    if any(isinstance(value, int) for value in counts.values()):
        _STEP_COUNTS_CACHE[cache_key] = counts
        if len(_STEP_COUNTS_CACHE) > _STEP_COUNTS_CACHE_MAX:
            _STEP_COUNTS_CACHE.popitem(last=False)

    return counts

