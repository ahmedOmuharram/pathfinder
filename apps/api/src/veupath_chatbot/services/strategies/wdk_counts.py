"""WDK step counts helpers."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)

_STEP_COUNTS_CACHE: OrderedDict[str, dict[str, int | None]] = OrderedDict()
_STEP_COUNTS_CACHE_MAX = 20


def _plan_cache_key(site_id: str, plan: JSONObject) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{site_id}:{digest}"


async def compute_step_counts_for_plan(
    plan: JSONObject,
    strategy_ast: StrategyAST,
    site_id: str,
) -> dict[str, int | None]:
    cache_key = _plan_cache_key(site_id, plan)
    cached = _STEP_COUNTS_CACHE.get(cache_key)
    if cached is not None and any(isinstance(value, int) for value in cached.values()):
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
    # Create a temporary (unsaved) WDK strategy, then fetch it once to read all
    # estimatedSize values in a single call instead of N individual report calls.
    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=result.step_tree,
            name="Pathfinder step counts",
            description=None,
            is_internal=True,
        )
        # WDK StrategyService.createStrategy returns { "id": <strategyId> }.
        if isinstance(created, dict):
            raw_id = created.get("id")
            if isinstance(raw_id, int):
                temp_strategy_id = raw_id
    except Exception:
        # Best-effort: if we can't create a strategy, counts will remain unknown.
        temp_strategy_id = None

    counts: dict[str, int | None] = {step.local_id: None for step in result.steps}

    # Fetch the strategy once — WDK includes estimatedSize on every step in the
    # strategy.steps dict, so one GET replaces N individual report POST calls.
    if temp_strategy_id is not None:
        try:
            wdk_strategy = await api.get_strategy(temp_strategy_id)
            if isinstance(wdk_strategy, dict):
                steps_dict = wdk_strategy.get("steps")
                if isinstance(steps_dict, dict):
                    for step in result.steps:
                        step_info = steps_dict.get(str(step.wdk_step_id))
                        if isinstance(step_info, dict):
                            estimated = step_info.get("estimatedSize")
                            if isinstance(estimated, int):
                                counts[step.local_id] = estimated
        except Exception as e:
            logger.warning("Failed to read counts from strategy payload", error=str(e))

    # Best-effort cleanup (avoid polluting the user's WDK account).
    if temp_strategy_id is not None:
        try:
            await api.delete_strategy(temp_strategy_id)
        except Exception as e:
            logger.warning(
                "Failed to delete temp WDK strategy during cleanup",
                temp_strategy_id=temp_strategy_id,
                error=str(e),
            )

    if any(isinstance(value, int) for value in counts.values()):
        _STEP_COUNTS_CACHE[cache_key] = counts
        if len(_STEP_COUNTS_CACHE) > _STEP_COUNTS_CACHE_MAX:
            _STEP_COUNTS_CACHE.popitem(last=False)

    return counts
