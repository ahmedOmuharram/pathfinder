"""WDK-backed strategy endpoints (open/import/sync/push/list)."""

from __future__ import annotations

from typing import Any
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
    _build_snapshot_from_wdk,
    _normalize_synced_parameters,
)
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.transport.http.deps import CurrentUser, OptionalUser, StrategyRepo, UserRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.transport.http.schemas import (
    OpenStrategyRequest,
    OpenStrategyResponse,
    PushResultResponse,
    StrategyResponse,
    WdkStrategySummaryResponse,
)
from veupath_chatbot.integrations.veupathdb.factory import get_site, list_sites

from ._shared import build_step_response

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.post("/open", response_model=OpenStrategyResponse)
async def open_strategy(
    request: OpenStrategyRequest,
    strategy_repo: StrategyRepo,
    user_repo: UserRepo,
    user_id: OptionalUser,
    response: Response,
):
    """Open a strategy by local or WDK strategy."""
    if user_id:
        await user_repo.get_or_create(user_id)
    else:
        user = await user_repo.create()
        user_id = user.id
        auth_token = create_user_token(user_id)
        response.set_cookie(
            key="pathfinder-auth",
            value=auth_token,
            httponly=True,
            samesite="lax",
        )

    if not request.strategy_id and not request.wdk_strategy_id:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[{"path": "siteId", "message": "Required", "code": "INVALID_PARAMETERS"}],
            )
        strategy = await strategy_repo.create(
            user_id=user_id,
            name="Draft Strategy",
            site_id=request.site_id,
            record_type=None,
            plan={},
            steps=[],
            root_step_id=None,
        )
    elif request.strategy_id:
        assert user_id is not None
        strategy = await get_owned_strategy_or_404(
            strategy_repo, request.strategy_id, user_id
        )
    else:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[{"path": "siteId", "message": "Required", "code": "INVALID_PARAMETERS"}],
            )
        try:
            api = get_strategy_api(request.site_id)
            wdk_strategy = await api.get_strategy(request.wdk_strategy_id)
        except Exception as e:
            logger.error("WDK fetch failed", error=str(e))
            raise WDKError("Failed to load WDK strategy")

        ast, steps_data = _build_snapshot_from_wdk(
            wdk_strategy, record_type_fallback="gene"
        )
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)

        existing = await strategy_repo.get_by_wdk_strategy_id(
            user_id, request.wdk_strategy_id
        )
        if existing:
            strategy = await strategy_repo.update(
                strategy_id=existing.id,
                name=ast.name or existing.name,
                plan=ast.to_dict(),
                steps=steps_data,
                root_step_id=ast.root.id,
                record_type=ast.record_type,
                wdk_strategy_id=request.wdk_strategy_id,
            )
            if not strategy:
                raise NotFoundError(
                    code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
                )
        else:
            strategy = await strategy_repo.create(
                user_id=user_id,
                name=ast.name or f"WDK Strategy {request.wdk_strategy_id}",
                site_id=request.site_id,
                record_type=ast.record_type,
                plan=ast.to_dict(),
                steps=steps_data,
                root_step_id=ast.root.id,
                wdk_strategy_id=request.wdk_strategy_id,
            )

    return OpenStrategyResponse(
        strategyId=str(strategy.id),
    )


@router.get("/wdk", response_model=list[WdkStrategySummaryResponse])
async def list_wdk_strategies(
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
):
    """List strategies from VEuPathDB WDK."""
    sites = [get_site(site_id)] if site_id else list_sites()
    results: list[dict[str, Any]] = []

    for site in sites:
        try:
            api = get_strategy_api(site.id)
            strategies = await api.list_strategies()
            for item in strategies:
                wdk_id = item.get("strategyId") or item.get("id")
                if not wdk_id:
                    continue
                root_step_id = item.get("rootStepId")
                is_saved = item.get("isSaved")
                if is_saved is None:
                    is_saved = item.get("is_saved")
                name = item.get("name") or f"WDK Strategy {wdk_id}"
                is_temporary = bool(is_saved is False or name == "Pathfinder step counts")
                results.append(
                    {
                        "wdkStrategyId": wdk_id,
                        "name": name,
                        "siteId": site.id,
                        "wdkUrl": site.strategy_url(wdk_id, root_step_id)
                        if wdk_id
                        else None,
                        "rootStepId": root_step_id,
                        "isSaved": is_saved,
                        "isTemporary": is_temporary,
                    }
                )
        except Exception as e:
            logger.warning("WDK strategy list failed", site_id=site.id, error=str(e))

    return results


@router.delete("/wdk/{wdkStrategyId}", status_code=204)
async def delete_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
):
    """Delete a strategy from VEuPathDB WDK."""
    try:
        api = get_strategy_api(siteId)
        await api.delete_strategy(wdkStrategyId)
    except Exception as e:
        logger.error("WDK strategy delete failed", error=str(e))
        raise WDKError("Failed to delete strategy from VEuPathDB")
    return Response(status_code=204)


@router.post("/wdk/{wdkStrategyId}/import", response_model=StrategyResponse)
async def import_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Import a WDK strategy as a local snapshot."""
    try:
        api = get_strategy_api(siteId)
        wdk_strategy = await api.get_strategy(wdkStrategyId)

        ast, steps_data = _build_snapshot_from_wdk(
            wdk_strategy, record_type_fallback="gene"
        )

        created = await strategy_repo.create(
            user_id=user_id,
            name=ast.name or f"WDK Strategy {wdkStrategyId}",
            title=ast.name or f"WDK Strategy {wdkStrategyId}",
            site_id=siteId,
            record_type=ast.record_type,
            plan=ast.to_dict(),
            steps=steps_data,
            root_step_id=ast.root.id,
            wdk_strategy_id=wdkStrategyId,
        )

        description = (
            (created.plan or {}).get("metadata", {}).get("description")
            if isinstance(created.plan, dict)
            else None
        )
        return StrategyResponse(
            id=created.id,
            name=created.name,
            title=created.title,
            description=description,
            siteId=created.site_id,
            recordType=created.record_type,
            steps=[build_step_response(s) for s in created.steps],
            rootStepId=created.root_step_id,
            wdkStrategyId=created.wdk_strategy_id,
            messages=created.messages,
            thinking=created.thinking,
            createdAt=created.created_at,
            updatedAt=created.updated_at,
        )
    except Exception as e:
        logger.error("WDK import failed", error=str(e))
        raise WDKError("Failed to import strategy from WDK")


@router.post("/{strategyId:uuid}/push", response_model=PushResultResponse)
async def push_to_wdk(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
):
    """Push strategy to VEuPathDB WDK."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")

    try:
        plan = strategy.plan if isinstance(strategy.plan, dict) else {}
        strategy_ast = validate_plan_or_raise(plan)

        api = get_strategy_api(strategy.site_id)

        result = await compile_strategy(strategy_ast, api, site_id=strategy.site_id)

        if strategy.wdk_strategy_id is not None:
            await api.update_strategy(
                strategy_id=strategy.wdk_strategy_id,
                step_tree=result.step_tree,
                name=strategy.name,
            )
            wdk_strategy_id = strategy.wdk_strategy_id
        else:
            wdk_result = await api.create_strategy(
                step_tree=result.step_tree,
                name=strategy.name,
                description=strategy_ast.description,
            )
            wdk_strategy_id = wdk_result.get("strategyId") or wdk_result.get("id")

        compiled_map = {s.local_id: s.wdk_step_id for s in result.steps}
        step_counts: dict[int, int] = {}
        for wdk_step_id in compiled_map.values():
            if not wdk_step_id:
                continue
            try:
                count = await api.get_step_count(wdk_step_id)
            except Exception:
                continue
            if isinstance(count, int):
                step_counts[wdk_step_id] = count
        steps_with_wdk = []
        for step in strategy.steps:
            local_id = step.get("id")
            step_data = dict(step)
            if local_id in compiled_map:
                step_data["wdkStepId"] = compiled_map[local_id]
                wdk_step_id = compiled_map[local_id]
                if wdk_step_id in step_counts:
                    step_data["resultCount"] = step_counts[wdk_step_id]
            steps_with_wdk.append(step_data)

        for step in strategy_ast.get_all_steps():
            wdk_step_id = compiled_map.get(step.id)
            if not wdk_step_id:
                continue
            for step_filter in getattr(step, "filters", []) or []:
                await api.set_step_filter(
                    step_id=wdk_step_id,
                    filter_name=step_filter.name,
                    value=step_filter.value,
                    disabled=step_filter.disabled,
                )
            for analysis in getattr(step, "analyses", []) or []:
                await api.run_step_analysis(
                    step_id=wdk_step_id,
                    analysis_type=analysis.analysis_type,
                    parameters=analysis.parameters,
                    custom_name=analysis.custom_name,
                )
            for report in getattr(step, "reports", []) or []:
                await api.run_step_report(
                    step_id=wdk_step_id,
                    report_name=report.report_name,
                    config=report.config,
                )

        await strategy_repo.update(
            strategy_id=strategyId,
            wdk_strategy_id=wdk_strategy_id,
            wdk_strategy_id_set=True,
            steps=steps_with_wdk,
        )

        site = get_site(strategy.site_id)
        wdk_url = site.strategy_url(wdk_strategy_id, result.root_step_id)

        return PushResultResponse(
            wdkStrategyId=wdk_strategy_id,
            wdkUrl=wdk_url,
        )

    except AppError:
        raise
    except Exception as e:
        logger.error("Push to WDK failed", error=str(e))
        raise WDKError(f"WDK error: {e}")


@router.post("/{strategyId:uuid}/sync-wdk", response_model=StrategyResponse)
async def sync_strategy_from_wdk(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
):
    """Sync local strategy snapshot from VEuPathDB WDK."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
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

        ast, steps_data = _build_snapshot_from_wdk(
            wdk_strategy, record_type_fallback=strategy.record_type
        )
        await _normalize_synced_parameters(ast, steps_data, api)
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)
        ast.name = ast.name or strategy.name

        updated = await strategy_repo.update(
            strategy_id=strategyId,
            name=ast.name or strategy.name,
            plan=ast.to_dict(),
            steps=steps_data,
            root_step_id=ast.root.id,
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )

        description = (
            (updated.plan or {}).get("metadata", {}).get("description")
            if isinstance(updated.plan, dict)
            else None
        )
        return StrategyResponse(
            id=updated.id,
            name=updated.name,
            description=description,
            siteId=updated.site_id,
            recordType=updated.record_type,
            steps=[build_step_response(s) for s in updated.steps],
            rootStepId=updated.root_step_id,
            wdkStrategyId=updated.wdk_strategy_id,
            createdAt=updated.created_at,
            updatedAt=updated.updated_at,
        )
    except AppError:
        raise
    except Exception as e:
        logger.error("WDK sync failed", error=str(e))
        raise WDKError("Failed to sync strategy from WDK")

