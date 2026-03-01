"""Shared helpers for strategies routers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from veupath_chatbot.integrations.veupathdb.strategy_api import (
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.strategies.serialization import count_steps_in_plan
from veupath_chatbot.transport.http.schemas import (
    MessageResponse,
    StepResponse,
    StrategyResponse,
    StrategySummaryResponse,
    ThinkingResponse,
)

if TYPE_CHECKING:
    from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
    from veupath_chatbot.persistence.models import Strategy

logger = get_logger(__name__)


def build_step_response(step: JSONObject) -> StepResponse:
    """Build a StepResponse from a step dict."""
    return StepResponse.model_validate(cast(dict[str, object], step))


def extract_plan_description(plan: JSONObject) -> str | None:
    """Extract ``plan["metadata"]["description"]`` with isinstance guards."""
    metadata_raw = plan.get("metadata")
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    desc_raw = metadata.get("description")
    return desc_raw if isinstance(desc_raw, str) else None


def parse_messages(raw: JSONArray | None) -> list[MessageResponse] | None:
    """Parse a strategy's ``messages`` JSON array into response models.

    Returns ``None`` on empty input or validation errors.
    """
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return [
            MessageResponse.model_validate(msg) for msg in raw if isinstance(msg, dict)
        ]
    except Exception:
        return None


def parse_thinking(raw: JSONObject | None) -> ThinkingResponse | None:
    """Parse a strategy's ``thinking`` JSON object into a response model.

    Returns ``None`` on empty input or validation errors.
    """
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return ThinkingResponse.model_validate(raw)
    except Exception:
        return None


def extract_wdk_is_saved(payload: JSONObject) -> bool:
    """Extract ``payload["isSaved"]`` with isinstance guard, defaults False."""
    raw = payload.get("isSaved") if isinstance(payload, dict) else None
    return bool(raw) if isinstance(raw, bool) else False


def extract_root_step_id(
    plan: JSONObject, fallback_root_step_id: str | None
) -> str | None:
    """Extract ``plan["root"]["id"]`` with isinstance guards.

    Falls back to ``fallback_root_step_id`` when the plan doesn't contain one.
    """
    root_raw = plan.get("root")
    root = root_raw if isinstance(root_raw, dict) else {}
    root_id_raw = root.get("id")
    root_step_id = root_id_raw if isinstance(root_id_raw, str) else None
    return root_step_id or fallback_root_step_id


def build_strategy_response(
    strategy: Strategy,
    *,
    plan: JSONObject,
    steps_data: JSONArray,
    root_step_id: str | None,
) -> StrategyResponse:
    """Build a ``StrategyResponse`` from an ORM strategy and pre-extracted data.

    This is the single canonical builder — replaces 5 divergent construction
    sites across ``crud.py`` and ``wdk_import.py``.
    """
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        description=extract_plan_description(plan),
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        steps=[build_step_response(s) for s in steps_data if isinstance(s, dict)],
        rootStepId=root_step_id,
        wdkStrategyId=strategy.wdk_strategy_id,
        isSaved=strategy.is_saved,
        messages=parse_messages(strategy.messages),
        thinking=parse_thinking(strategy.thinking),
        modelId=strategy.model_id,
        createdAt=strategy.created_at or datetime.now(UTC),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(UTC),
    )


def build_summary_response(strategy: Strategy) -> StrategySummaryResponse:
    """Build a ``StrategySummaryResponse`` from an ORM strategy."""
    return StrategySummaryResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        stepCount=(
            count_steps_in_plan(strategy.plan or {})
            or (len(strategy.steps or []) if strategy.steps else 0)
        ),
        resultCount=strategy.result_count,
        wdkStrategyId=strategy.wdk_strategy_id,
        isSaved=strategy.is_saved,
        createdAt=strategy.created_at or datetime.now(UTC),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(UTC),
    )


async def cleanup_internal_control_test_strategies(
    api: StrategyAPI,
    wdk_items: JSONArray,
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
        except Exception as e:
            logger.warning(
                "Failed to delete leaked internal control-test strategy",
                site_id=site_id,
                wdk_strategy_id=wdk_id,
                error=str(e),
            )
