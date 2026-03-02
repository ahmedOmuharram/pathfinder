"""WDK-backed strategy endpoints (open/import/sync/list)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

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
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
    _build_snapshot_from_wdk,
    _normalize_synced_parameters,
)
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    StrategyRepo,
)
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.schemas import (
    OpenStrategyRequest,
    OpenStrategyResponse,
    StrategyResponse,
    StrategySummaryResponse,
    WdkStrategySummaryResponse,
)

from ._shared import (
    build_strategy_response,
    build_summary_response,
    cleanup_internal_control_test_strategies,
    extract_wdk_is_saved,
)
from .wdk_import_logic import (
    _is_internal_control_test_name as _is_internal_control_test_name,
)
from .wdk_import_logic import (
    _parse_wdk_strategy_id,
    _sync_single_wdk_strategy,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.post("/open", response_model=OpenStrategyResponse)
async def open_strategy(
    request: OpenStrategyRequest,
    strategy_repo: StrategyRepo,
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
        strategy = await strategy_repo.create(
            user_id=user_id,
            name="Draft Strategy",
            site_id=request.site_id,
            record_type=None,
            plan={},
        )
    elif request.strategy_id:
        strategy = await get_owned_strategy_or_404(
            strategy_repo, request.strategy_id, user_id
        )
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
            strategy = await _sync_single_wdk_strategy(
                wdk_id=request.wdk_strategy_id,
                site_id=request.site_id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
        except WDKError as e:
            logger.error("WDK fetch failed", error=str(e))
            raise
        except Exception as e:
            logger.error("WDK fetch failed", error=str(e))
            raise WDKError(f"Failed to load WDK strategy: {e}") from e

    return OpenStrategyResponse(
        strategyId=strategy.id,
    )


@router.get("/wdk", response_model=list[WdkStrategySummaryResponse])
async def list_wdk_strategies(
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
                wdk_id_int = _parse_wdk_strategy_id(item)
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


@router.post("/sync-wdk", response_model=list[StrategySummaryResponse])
async def sync_all_wdk_strategies(
    site_id: Annotated[str, Query(alias="siteId")],
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> list[StrategySummaryResponse]:
    """Batch-sync all WDK strategies into the local DB and return the full list.

    For each non-internal WDK strategy, fetches the full payload and upserts
    a local copy. Returns the complete list of local strategies for this site
    (including non-WDK drafts).
    """
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
        wdk_id = _parse_wdk_strategy_id(item)
        if wdk_id is None:
            continue
        name_raw = item.get("name")
        name = name_raw if isinstance(name_raw, str) else ""
        if is_internal_wdk_strategy_name(name):
            continue
        synced_wdk_ids.add(wdk_id)
        try:
            await _sync_single_wdk_strategy(
                wdk_id=wdk_id,
                site_id=site.id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to sync WDK strategy",
                wdk_id=wdk_id,
                site_id=site.id,
                error=str(e),
            )

    # Tombstone: remove local strategies whose WDK counterparts no longer exist.
    # Only prune if we successfully fetched from WDK (wdk_items is non-empty).
    if wdk_items:
        try:
            pruned = await strategy_repo.prune_wdk_orphans(
                user_id, site.id, synced_wdk_ids
            )
            if pruned:
                logger.info(
                    "Pruned orphaned local strategies",
                    site_id=site.id,
                    pruned_count=pruned,
                )
        except Exception as e:
            logger.warning(
                "Failed to prune orphaned strategies",
                site_id=site.id,
                error=str(e),
            )

    # Return the full local list (now includes all synced WDK strategies).
    strategies = await strategy_repo.list_by_user(user_id, site_id)
    return [build_summary_response(s) for s in strategies]


@router.delete("/wdk/{wdkStrategyId}", status_code=204, response_class=Response)
async def delete_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
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
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Import a WDK strategy as a local snapshot.

    Upserts: if a local row already exists for this WDK strategy ID
    (e.g. from a previous sync or double-click), it is updated rather
    than creating a duplicate.
    """
    try:
        api = get_strategy_api(siteId)
        wdk_strategy = await api.get_strategy(wdkStrategyId)

        ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)
        is_saved = extract_wdk_is_saved(wdk_strategy)

        # Upsert: check if we already have a local copy.
        existing = await strategy_repo.get_by_wdk_strategy_id(user_id, wdkStrategyId)
        if existing:
            created = await strategy_repo.update(
                strategy_id=existing.id,
                name=ast.name or existing.name,
                plan=ast.to_dict(),
                record_type=ast.record_type,
                wdk_strategy_id=wdkStrategyId,
                wdk_strategy_id_set=True,
                is_saved=is_saved,
                is_saved_set=True,
            )
            if not created:
                raise NotFoundError(
                    code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
                )
            await strategy_repo.refresh(created)
        else:
            created = await strategy_repo.create(
                user_id=user_id,
                name=ast.name or f"WDK Strategy {wdkStrategyId}",
                title=ast.name or f"WDK Strategy {wdkStrategyId}",
                site_id=siteId,
                record_type=ast.record_type,
                plan=ast.to_dict(),
                wdk_strategy_id=wdkStrategyId,
                is_saved=is_saved,
            )

        plan_dict: JSONObject = created.plan if isinstance(created.plan, dict) else {}

        return build_strategy_response(
            created,
            plan=plan_dict,
            steps_data=steps_data,
            root_step_id=ast.root.id,
        )
    except AppError:
        raise
    except WDKError as e:
        logger.error("WDK import failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK import failed", error=str(e))
        raise WDKError(f"Failed to import strategy from WDK: {e}") from e


@router.post("/{strategyId:uuid}/sync-wdk", response_model=StrategyResponse)
async def sync_strategy_from_wdk(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
) -> StrategyResponse:
    """Sync local strategy snapshot from VEuPathDB WDK."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    if not strategy.wdk_strategy_id:
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

    try:
        api = get_strategy_api(strategy.site_id)
        wdk_strategy = await api.get_strategy(strategy.wdk_strategy_id)

        ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)
        await _normalize_synced_parameters(ast, steps_data, api)
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)
        ast.name = ast.name or strategy.name

        is_saved = extract_wdk_is_saved(wdk_strategy)

        updated = await strategy_repo.update(
            strategy_id=strategyId,
            name=ast.name or strategy.name,
            plan=ast.to_dict(),
            is_saved=is_saved,
            is_saved_set=True,
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )

        plan_dict: JSONObject = updated.plan if isinstance(updated.plan, dict) else {}

        return build_strategy_response(
            updated,
            plan=plan_dict,
            steps_data=steps_data,
            root_step_id=ast.root.id,
        )
    except AppError:
        raise
    except WDKError as e:
        logger.error("WDK sync failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK sync failed", error=str(e))
        raise WDKError(f"Failed to sync strategy from WDK: {e}") from e
