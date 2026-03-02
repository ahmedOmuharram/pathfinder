"""WDK strategy business logic (no FastAPI dependencies)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from veupath_chatbot.persistence.models import Strategy

from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.errors import (
    ErrorCode,
    NotFoundError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
    _build_snapshot_from_wdk,
    _normalize_synced_parameters,
)
from veupath_chatbot.transport.http.deps import (
    StrategyRepo,
)

from ._shared import (
    extract_wdk_is_saved,
)

logger = get_logger(__name__)


async def _sync_single_wdk_strategy(
    *,
    wdk_id: int,
    site_id: str,
    api: StrategyAPI,
    strategy_repo: StrategyRepo,
    user_id: UUID,
) -> Strategy:
    """Fetch a single WDK strategy and upsert a local copy.

    Shared by ``open_strategy`` and ``sync_all_wdk_strategies``.
    """

    wdk_strategy = await api.get_strategy(wdk_id)

    ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)
    _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)

    # Normalize parameters so all sync paths produce consistent representations.
    try:
        await _normalize_synced_parameters(ast, steps_data, api)
    except Exception as exc:
        logger.warning(
            "Parameter normalization failed during sync, storing raw values",
            wdk_id=wdk_id,
            error=str(exc),
        )

    is_saved = extract_wdk_is_saved(wdk_strategy)

    existing = await strategy_repo.get_by_wdk_strategy_id(user_id, wdk_id)
    if existing:
        updated = await strategy_repo.update(
            strategy_id=existing.id,
            name=ast.name or existing.name,
            plan=ast.to_dict(),
            record_type=ast.record_type,
            wdk_strategy_id=wdk_id,
            wdk_strategy_id_set=True,
            is_saved=is_saved,
            is_saved_set=True,
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        # Refresh to get server-side updated_at for correct sidebar sort order.
        await strategy_repo.refresh(updated)
        return updated
    else:
        return await strategy_repo.create(
            user_id=user_id,
            name=ast.name or f"WDK Strategy {wdk_id}",
            site_id=site_id,
            record_type=ast.record_type,
            plan=ast.to_dict(),
            wdk_strategy_id=wdk_id,
            is_saved=is_saved,
        )


def _parse_wdk_strategy_id(item: JSONObject) -> int | None:
    """Extract integer WDK strategy ID from a list-strategies item.

    WDK's ``StrategyFormatter`` emits ``strategyId`` (``JsonKeys.STRATEGY_ID``)
    as a Java long (always an int in JSON).

    :param item: Item dict.

    """
    wdk_id = item.get("strategyId")
    if isinstance(wdk_id, int):
        return wdk_id
    return None


def _is_internal_control_test_name(name: str | None) -> bool:
    if not isinstance(name, str):
        return False
    if not is_internal_wdk_strategy_name(name):
        return False
    return strip_internal_wdk_strategy_name(name).startswith("Pathfinder control test")
