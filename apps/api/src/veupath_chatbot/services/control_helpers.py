"""Formatting and parsing utilities for control-test evaluation."""

import json

from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.types import ControlValueFormat

logger = get_logger(__name__)


def _encode_id_list(ids: list[str], fmt: ControlValueFormat) -> str:
    cleaned = [str(x).strip() for x in ids if str(x).strip()]
    if fmt == "newline":
        return "\n".join(cleaned)
    if fmt == "comma":
        return ",".join(cleaned)
    # json_list
    return json.dumps(cleaned)


async def delete_temp_strategy(api: StrategyAPI, strategy_id: int | None) -> None:
    """Best-effort deletion of a temporary WDK strategy.

    Silently logs and swallows errors — callers should use this in
    ``finally`` blocks to avoid masking the original exception.
    """
    if strategy_id is None:
        return
    try:
        await api.delete_strategy(strategy_id)
    except (AppError, ValueError, TypeError) as exc:
        logger.warning(
            "Failed to delete temp WDK strategy during cleanup",
            temp_strategy_id=strategy_id,
            error=str(exc),
        )


async def _get_total_count_for_step(api: StrategyAPI, step_id: int) -> int | None:
    """Get totalCount for a step. Returns None on failure."""
    try:
        return await api.get_step_count(step_id)
    except (AppError, ValueError, TypeError) as exc:
        logger.debug(
            "Failed to get total count for step", step_id=step_id, error=str(exc)
        )
        return None


async def cleanup_internal_control_test_strategies(
    api: StrategyAPI,
    wdk_items: object,
    *,
    site_id: str = "",
) -> None:
    """Delete leaked internal control-test strategies from a WDK item list.

    Callers fetch the item list themselves (via ``api.list_strategies()``),
    then pass it here for cleanup.
    """
    if not isinstance(wdk_items, list):
        return
    for item in wdk_items:
        if not isinstance(item, dict):
            continue
        name_raw = item.get("name")
        name = name_raw if isinstance(name_raw, str) else None
        if not isinstance(name, str) or not is_internal_wdk_strategy_name(name):
            continue
        display_name = strip_internal_wdk_strategy_name(name)
        if not display_name.startswith("Pathfinder control test"):
            continue
        wdk_id = item.get("strategyId")
        if not isinstance(wdk_id, int):
            continue
        try:
            await api.delete_strategy(wdk_id)
            logger.info(
                "Deleted leaked internal control-test WDK strategy",
                site_id=site_id,
                wdk_strategy_id=wdk_id,
            )
        except (AppError, ValueError, TypeError) as e:
            logger.warning(
                "Failed to delete leaked internal control-test strategy",
                site_id=site_id,
                wdk_strategy_id=wdk_id,
                error=str(e),
            )
