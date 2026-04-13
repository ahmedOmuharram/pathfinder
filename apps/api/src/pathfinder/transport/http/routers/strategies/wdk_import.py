"""WDK-backed strategy endpoints (open/import/sync/list)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query
from shared_py.defaults import DEFAULT_STREAM_NAME

from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.control_helpers import (
    cleanup_internal_control_test_strategies,
)
from pathfinder.services.strategies.auto_import import (
    background_auto_import_gene_sets,
)
from pathfinder.services.strategies.wdk_sync import (
    sync_to_chat,
    upsert_summary_chat,
)
from pathfinder.services.wdk import (
    get_site,
    get_strategy_api,
    is_internal_wdk_strategy_name,
)
from pathfinder.transport.http.deps import (
    ChatRepo,
    CurrentUser,
)
from pathfinder.transport.http.schemas import (
    OpenStrategyRequest,
    OpenStrategyResponse,
    StrategyResponse,
)

from ._shared import build_chat_summary

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.post("/open", response_model=OpenStrategyResponse)
async def open_strategy(
    request: OpenStrategyRequest,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> OpenStrategyResponse:
    """Open a strategy by local id or WDK strategy id."""
    if not request.strategy_id and not request.wdk_strategy_id:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[
                    {
                        "path": "siteId",
                        "message": "Required",
                        "code": "INVALID_PARAMETERS",
                    }
                ],
            )
        chat = await chat_repo.create(
            user_id=user_id,
            site_id=request.site_id,
            name=DEFAULT_STREAM_NAME,
        )
        return OpenStrategyResponse(strategyId=chat.id)

    if request.strategy_id:
        chat = await chat_repo.get_by_id(request.strategy_id)
        if not chat:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        if chat.user_id != user_id:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        return OpenStrategyResponse(strategyId=chat.id)

    if not request.site_id:
        raise ValidationError(
            detail="siteId is required",
            errors=[
                {
                    "path": "siteId",
                    "message": "Required",
                    "code": "INVALID_PARAMETERS",
                }
            ],
        )
    if request.wdk_strategy_id is None:
        raise ValidationError(
            detail="wdk_strategy_id is required",
            errors=[
                {
                    "path": "wdk_strategy_id",
                    "message": "Required",
                    "code": "INVALID_PARAMETERS",
                }
            ],
        )
    try:
        api = get_strategy_api(request.site_id)
        chat = await sync_to_chat(
            wdk_id=request.wdk_strategy_id,
            site_id=request.site_id,
            api=api,
            chat_repo=chat_repo,
            user_id=user_id,
        )
    except WDKError as e:
        logger.exception("WDK fetch failed", error=str(e))
        raise
    except Exception as e:
        logger.exception("WDK fetch failed", error=str(e))
        msg = f"Failed to load WDK strategy: {e}"
        raise WDKError(msg) from e

    return OpenStrategyResponse(strategyId=chat.id)


@router.post("/sync-wdk", response_model=list[StrategyResponse])
async def sync_all_wdk_strategies(
    site_id: Annotated[str, Query(alias="siteId")],
    chat_repo: ChatRepo,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
) -> list[StrategyResponse]:
    """Batch-sync all WDK strategies into the chats table and return the full list."""
    site = get_site(site_id)
    try:
        api = get_strategy_api(site.id)
        wdk_items = await api.list_strategies()
        await cleanup_internal_control_test_strategies(api, wdk_items, site_id=site.id)
    except (AppError, OSError, RuntimeError) as e:
        logger.warning("WDK list failed during sync", site_id=site.id, error=str(e))
        wdk_items = []

    synced_wdk_ids: set[int] = set()
    for item in wdk_items:
        if is_internal_wdk_strategy_name(item.name):
            continue
        synced_wdk_ids.add(item.strategy_id)
        try:
            async with chat_repo.session.begin_nested():
                await upsert_summary_chat(
                    item,
                    chat_repo=chat_repo,
                    user_id=user_id,
                    site_id=site.id,
                )
        except (AppError, OSError, RuntimeError) as e:
            logger.warning(
                "Failed to sync WDK strategy",
                wdk_id=item.strategy_id,
                site_id=site.id,
                error=str(e),
            )

    if wdk_items:
        try:
            async with chat_repo.session.begin_nested():
                pruned = await chat_repo.prune_wdk_orphans(
                    user_id, site.id, synced_wdk_ids
                )
                if pruned:
                    logger.info(
                        "Pruned orphaned chats",
                        site_id=site.id,
                        pruned_count=pruned,
                    )
        except (AppError, OSError, RuntimeError) as e:
            logger.warning(
                "Failed to prune orphaned chats",
                site_id=site.id,
                error=str(e),
            )

    chats = await chat_repo.list_chats(user_id, site_id)

    # Commit the session so all locks are released before the background task
    # opens its own session — prevents deadlock between the prune DELETE and
    # the auto-import's concurrent SELECT/UPDATE on the same tables.
    await chat_repo.session.commit()

    background_tasks.add_task(
        background_auto_import_gene_sets, site_id=site.id, user_id=user_id
    )

    return [build_chat_summary(c, site_id=site_id) for c in chats]
