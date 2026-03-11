"""WDK-backed strategy endpoints (open/import/sync/list)."""

from typing import Annotated

from fastapi import APIRouter, Query
from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.platform.errors import (
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tasks import spawn
from veupath_chatbot.services.control_helpers import (
    cleanup_internal_control_test_strategies,
)
from veupath_chatbot.services.strategies.auto_import import (
    background_auto_import_gene_sets,
)
from veupath_chatbot.services.strategies.wdk_bridge import (
    parse_wdk_strategy_id,
    sync_to_projection,
    upsert_summary_projection,
)
from veupath_chatbot.services.wdk import (
    get_site,
    get_strategy_api,
    is_internal_wdk_strategy_name,
)
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    StreamRepo,
)
from veupath_chatbot.transport.http.schemas import (
    OpenStrategyRequest,
    OpenStrategyResponse,
    StrategyResponse,
)

from ._shared import build_projection_summary

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.post("/open", response_model=OpenStrategyResponse)
async def open_strategy(
    request: OpenStrategyRequest,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> OpenStrategyResponse:
    """Open a strategy by local or WDK strategy."""
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
        # New conversation: create Stream + StreamProjection.
        stream = await stream_repo.create(
            user_id=user_id,
            site_id=request.site_id,
            name=DEFAULT_STREAM_NAME,
        )
        return OpenStrategyResponse(strategyId=stream.id)

    elif request.strategy_id:
        # Verify the stream exists and belongs to user.
        projection = await stream_repo.get_projection(request.strategy_id)
        if not projection or not projection.stream:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        if projection.stream.user_id != user_id:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        return OpenStrategyResponse(strategyId=projection.stream_id)

    else:
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
            projection = await sync_to_projection(
                wdk_id=request.wdk_strategy_id,
                site_id=request.site_id,
                api=api,
                stream_repo=stream_repo,
                user_id=user_id,
            )
        except WDKError as e:
            logger.error("WDK fetch failed", error=str(e))
            raise
        except Exception as e:
            logger.error("WDK fetch failed", error=str(e))
            raise WDKError(f"Failed to load WDK strategy: {e}") from e

        return OpenStrategyResponse(strategyId=projection.stream_id)


@router.post("/sync-wdk", response_model=list[StrategyResponse])
async def sync_all_wdk_strategies(
    site_id: Annotated[str, Query(alias="siteId")],
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> list[StrategyResponse]:
    """Batch-sync all WDK strategies into the CQRS layer and return the full list."""
    site = get_site(site_id)
    try:
        api = get_strategy_api(site.id)
        wdk_items = await api.list_strategies()
        await cleanup_internal_control_test_strategies(api, wdk_items, site_id=site.id)
    except Exception as e:
        logger.warning("WDK list failed during sync", site_id=site.id, error=str(e))
        wdk_items = []

    synced_wdk_ids: set[int] = set()
    for item in wdk_items:
        if not isinstance(item, dict):
            continue
        wdk_id = parse_wdk_strategy_id(item)
        if wdk_id is None:
            continue
        name_raw = item.get("name")
        name = name_raw if isinstance(name_raw, str) else ""
        if is_internal_wdk_strategy_name(name):
            continue
        synced_wdk_ids.add(wdk_id)
        try:
            async with stream_repo.session.begin_nested():
                await upsert_summary_projection(
                    item,
                    stream_repo=stream_repo,
                    user_id=user_id,
                    site_id=site.id,
                )
        except Exception as e:
            logger.warning(
                "Failed to sync WDK strategy",
                wdk_id=wdk_id,
                site_id=site.id,
                error=str(e),
            )

    # Prune orphaned streams whose WDK counterparts no longer exist.
    if wdk_items:
        try:
            async with stream_repo.session.begin_nested():
                pruned = await stream_repo.prune_wdk_orphans(
                    user_id, site.id, synced_wdk_ids
                )
                if pruned:
                    logger.info(
                        "Pruned orphaned streams",
                        site_id=site.id,
                        pruned_count=pruned,
                    )
        except Exception as e:
            logger.warning(
                "Failed to prune orphaned streams",
                site_id=site.id,
                error=str(e),
            )

    # Auto-import gene sets in the background — don't block the response
    # while WDK API calls resolve gene IDs for each eligible strategy.
    spawn(
        background_auto_import_gene_sets(site_id=site.id, user_id=user_id),
        name=f"auto-import-gene-sets-{site.id}",
    )

    projections = await stream_repo.list_projections(user_id, site_id)
    return [build_projection_summary(p, site_id=site_id) for p in projections]
