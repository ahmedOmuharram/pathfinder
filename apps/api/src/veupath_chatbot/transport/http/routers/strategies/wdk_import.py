"""WDK-backed strategy endpoints (open/import/sync/list)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.integrations.veupathdb.factory import (
    get_site,
    get_strategy_api,
    list_sites,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.errors import (
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.control_helpers import (
    cleanup_internal_control_test_strategies,
)
from veupath_chatbot.services.strategies.wdk_bridge import (
    extract_wdk_is_saved,
    fetch_and_convert,
    parse_wdk_strategy_id,
    sync_to_projection,
    upsert_projection,
    wdk_error_boundary,
)
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    StreamRepo,
)
from veupath_chatbot.transport.http.schemas import (
    OpenStrategyRequest,
    OpenStrategyResponse,
    StrategyResponse,
    WdkStrategySummaryResponse,
)

from ._shared import (
    build_projection_response,
    build_projection_summary,
)

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


@router.get("/wdk", response_model=list[WdkStrategySummaryResponse])
async def list_wdk_strategies(
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[WdkStrategySummaryResponse]:
    """List strategies from VEuPathDB WDK."""
    sites = [get_site(site_id)] if site_id else list_sites()
    results: list[WdkStrategySummaryResponse] = []

    for site in sites:
        try:
            api = get_strategy_api(site.id)
            strategies = await api.list_strategies()
            for item in strategies:
                if not isinstance(item, dict):
                    continue
                wdk_id_int = parse_wdk_strategy_id(item)
                if wdk_id_int is None:
                    continue
                root_step_id_raw = item.get("rootStepId")
                root_step_id: int | None = (
                    root_step_id_raw if isinstance(root_step_id_raw, int) else None
                )
                is_saved = extract_wdk_is_saved(item)
                name_raw = item.get("name")
                name = (
                    name_raw
                    if isinstance(name_raw, str)
                    else f"WDK Strategy {wdk_id_int}"
                )
                is_internal = is_internal_wdk_strategy_name(name)
                if is_internal:
                    name = strip_internal_wdk_strategy_name(name)

                results.append(
                    WdkStrategySummaryResponse(
                        wdkStrategyId=wdk_id_int,
                        name=name,
                        siteId=site.id,
                        wdkUrl=site.strategy_url(wdk_id_int, root_step_id),
                        rootStepId=root_step_id,
                        isSaved=is_saved,
                        isInternal=is_internal,
                    )
                )
        except Exception as e:
            logger.warning("WDK strategy list failed", site_id=site.id, error=str(e))

    return results


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
                await sync_to_projection(
                    wdk_id=wdk_id,
                    site_id=site.id,
                    api=api,
                    stream_repo=stream_repo,
                    user_id=user_id,
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

    # Return from CQRS projections.
    projections = await stream_repo.list_projections(user_id, site_id)
    return [build_projection_summary(p, site_id=site_id) for p in projections]


@router.delete("/wdk/{wdkStrategyId}", status_code=204, response_class=Response)
async def delete_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
    user_id: CurrentUser,
) -> Response:
    """Delete a strategy from VEuPathDB WDK."""
    try:
        api = get_strategy_api(siteId)
        await api.delete_strategy(wdkStrategyId)
    except Exception as e:
        logger.error("WDK strategy delete failed", error=str(e))
        raise WDKError("Failed to delete strategy from VEuPathDB") from e
    return Response(status_code=204)


@router.post("/wdk/{wdkStrategyId}/import", response_model=StrategyResponse)
async def import_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Import a WDK strategy as a local snapshot (CQRS only).

    Upserts: if a stream already exists for this WDK strategy ID,
    it is updated rather than creating a duplicate.
    """
    async with wdk_error_boundary("import strategy from WDK"):
        api = get_strategy_api(siteId)
        ast, is_saved = await fetch_and_convert(api, wdkStrategyId)
        plan = ast.to_dict()
        name = ast.name or f"WDK Strategy {wdkStrategyId}"

        projection = await upsert_projection(
            stream_repo=stream_repo,
            user_id=user_id,
            site_id=siteId,
            wdk_id=wdkStrategyId,
            name=name,
            plan=plan,
            record_type=ast.record_type,
            is_saved=is_saved,
            step_count=len(ast.get_all_steps()),
        )

        return build_projection_response(projection)


@router.post("/{strategyId:uuid}/sync-wdk", response_model=StrategyResponse)
async def sync_strategy_from_wdk(
    strategyId: UUID,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Sync local stream projection from VEuPathDB WDK."""
    from .._authz import get_owned_projection_or_404

    projection = await get_owned_projection_or_404(stream_repo, strategyId, user_id)
    if not projection.wdk_strategy_id:
        raise ValidationError(
            detail="Strategy not linked to WDK",
            errors=[
                {
                    "path": "wdkStrategyId",
                    "message": "Strategy must be linked to WDK",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    site_id = projection.site_id
    if not site_id:
        raise ValidationError(
            detail="Stream has no site_id",
            errors=[
                {
                    "path": "siteId",
                    "message": "Stream must have a site_id",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    async with wdk_error_boundary("sync strategy from WDK"):
        api = get_strategy_api(site_id)
        ast, is_saved = await fetch_and_convert(api, projection.wdk_strategy_id)
        ast.name = ast.name or projection.name
        plan = ast.to_dict()

        await stream_repo.update_projection(
            strategyId,
            name=ast.name,
            plan=plan,
            record_type=ast.record_type,
            is_saved=is_saved,
            is_saved_set=True,
            step_count=len(ast.get_all_steps()),
        )

        updated = await stream_repo.get_projection(strategyId)
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )

        return build_projection_response(updated)
