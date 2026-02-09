"""WDK-backed strategy endpoints (open/import/sync/push/list)."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    find_input_step_param,
)
from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.integrations.veupathdb.factory import (
    get_site,
    get_strategy_api,
    list_sites,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StrategyAPI,
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
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
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
    MessageResponse,
    OpenStrategyRequest,
    OpenStrategyResponse,
    PushResultResponse,
    StepResponse,
    StrategyResponse,
    ThinkingResponse,
    WdkStrategySummaryResponse,
)

from ._shared import build_step_response

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


async def _validate_transform_steps_accept_input(
    *, strategy_ast: StrategyAST, api: StrategyAPI
) -> None:
    """Reject plans that encode non-input questions as transforms.

    Root cause we guard against: a node is structurally a transform (has primaryInput),
    but its WDK question does not define an input-step AnswerParam. WDK will then reject
    strategy creation with: "Step <id> does not allow a primary input step."
    """
    # StrategyAST/PlanStepNode are imported indirectly here; keep this helper tolerant.
    for step in getattr(strategy_ast, "get_all_steps", lambda: [])():
        try:
            kind = step.infer_kind()
        except Exception:
            continue
        if kind != "transform":
            continue
        record_type = getattr(strategy_ast, "record_type", None)
        search_name = getattr(step, "search_name", None)
        if not isinstance(record_type, str) or not record_type:
            continue
        if not isinstance(search_name, str) or not search_name:
            continue
        # Placeholder used in internal graph representations; not a real WDK question.
        if search_name == "__combine__":
            continue
        try:
            details = await api.client.get_search_details(
                record_type, search_name, expand_params=True
            )
        except Exception:
            # If we cannot load metadata, let compilation surface a clearer upstream error.
            continue
        details_dict: JSONObject
        if isinstance(details, dict):
            search_data_raw = details.get("searchData")
            if isinstance(search_data_raw, dict):
                details_dict = search_data_raw
            else:
                details_dict = details
        else:
            details_dict = {}
        specs = adapt_param_specs(details_dict)
        if not find_input_step_param(specs):
            raise ValidationError(
                title="Invalid plan",
                detail=f"Step '{search_name}' cannot be used as a transform in WDK (no input-step parameter).",
                errors=[
                    {
                        "path": "plan.root",
                        "code": ErrorCode.INVALID_STRATEGY.value,
                        "recordType": record_type,
                        "searchName": search_name,
                        "stepId": getattr(step, "id", None),
                        "message": "Transform steps must reference a WDK question that accepts an input step.",
                    }
                ],
            )


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
            wdk_strategy = await api.get_strategy(request.wdk_strategy_id)
        except WDKError as e:
            # Preserve upstream status/detail for debugging (e.g. 403/404 from WDK).
            logger.error("WDK fetch failed", error=str(e))
            raise
        except Exception as e:
            logger.error("WDK fetch failed", error=str(e))
            raise WDKError(f"Failed to load WDK strategy: {e}") from e

        ast, steps_data = _build_snapshot_from_wdk(
            wdk_strategy, record_type_fallback="gene"
        )
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)

        existing = await strategy_repo.get_by_wdk_strategy_id(
            user_id, request.wdk_strategy_id
        )
        if existing:
            updated_strategy = await strategy_repo.update(
                strategy_id=existing.id,
                name=ast.name or existing.name,
                plan=ast.to_dict(),
                record_type=ast.record_type,
                wdk_strategy_id=request.wdk_strategy_id,
                wdk_strategy_id_set=True,
            )
            if not updated_strategy:
                raise NotFoundError(
                    code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
                )
            strategy = updated_strategy
        else:
            strategy = await strategy_repo.create(
                user_id=user_id,
                name=ast.name or f"WDK Strategy {request.wdk_strategy_id}",
                site_id=request.site_id,
                record_type=ast.record_type,
                plan=ast.to_dict(),
                wdk_strategy_id=request.wdk_strategy_id,
            )

    return OpenStrategyResponse(
        strategyId=strategy.id,
    )


@router.get("/wdk", response_model=list[WdkStrategySummaryResponse])
async def list_wdk_strategies(
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[WdkStrategySummaryResponse]:
    """List strategies from VEuPathDB WDK."""
    sites = [get_site(site_id)] if site_id else list_sites()
    results: JSONArray = []

    for site in sites:
        try:
            api = get_strategy_api(site.id)
            strategies = await api.list_strategies()
            for item in strategies:
                if not isinstance(item, dict):
                    continue
                strategy_id_raw = item.get("strategyId")
                id_raw = item.get("id")
                wdk_id = strategy_id_raw or id_raw
                if not wdk_id:
                    continue
                wdk_id_int: int
                if isinstance(wdk_id, int):
                    wdk_id_int = wdk_id
                elif isinstance(wdk_id, str) and wdk_id.isdigit():
                    wdk_id_int = int(wdk_id)
                else:
                    continue
                root_step_id_raw = item.get("rootStepId")
                root_step_id: int | None = (
                    root_step_id_raw if isinstance(root_step_id_raw, int) else None
                )
                is_saved_raw = item.get("isSaved")
                is_saved: bool | None = (
                    bool(is_saved_raw) if isinstance(is_saved_raw, bool) else None
                )
                if is_saved is None:
                    is_saved_raw2 = item.get("is_saved")
                    is_saved = (
                        bool(is_saved_raw2) if isinstance(is_saved_raw2, bool) else None
                    )
                name_raw = item.get("name")
                name = (
                    name_raw
                    if isinstance(name_raw, str)
                    else f"WDK Strategy {wdk_id_int}"
                )
                is_internal = is_internal_wdk_strategy_name(name)
                if is_internal:
                    name = strip_internal_wdk_strategy_name(name)
                from veupath_chatbot.transport.http.schemas import (
                    WdkStrategySummaryResponse,
                )

                results.append(
                    cast(
                        JSONValue,
                        WdkStrategySummaryResponse(
                            wdkStrategyId=wdk_id_int,
                            name=name,
                            siteId=site.id,
                            wdkUrl=site.strategy_url(wdk_id_int, root_step_id),
                            rootStepId=root_step_id,
                            isSaved=is_saved,
                            isInternal=is_internal,
                        ).model_dump(),
                    )
                )
        except Exception as e:
            logger.warning("WDK strategy list failed", site_id=site.id, error=str(e))

    from veupath_chatbot.transport.http.schemas import WdkStrategySummaryResponse

    return [
        WdkStrategySummaryResponse.model_validate(r)
        if isinstance(r, dict)
        else WdkStrategySummaryResponse(
            wdkStrategyId=0,
            name="",
            siteId="",
            wdkUrl="",
            rootStepId=None,
            isSaved=None,
            isInternal=False,
        )
        for r in results
        if isinstance(r, dict)
    ]


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
            wdk_strategy_id=wdkStrategyId,
        )

        plan_dict: JSONObject = created.plan if isinstance(created.plan, dict) else {}
        metadata_raw = plan_dict.get("metadata")
        metadata: JSONObject = metadata_raw if isinstance(metadata_raw, dict) else {}
        description_raw = metadata.get("description")
        description: str | None = (
            description_raw if isinstance(description_raw, str) else None
        )

        steps_responses: list[StepResponse] = []
        for s in steps_data:
            if isinstance(s, dict):
                steps_responses.append(build_step_response(s))

        from veupath_chatbot.transport.http.schemas import (
            MessageResponse,
            ThinkingResponse,
        )

        messages_list: list[MessageResponse] | None = None
        if created.messages:
            messages_list = [
                MessageResponse.model_validate(m)
                if isinstance(m, dict)
                else MessageResponse(role="user", content="")
                for m in created.messages
                if isinstance(m, dict)
            ]

        thinking_obj: ThinkingResponse | None = None
        if isinstance(created.thinking, dict):
            thinking_obj = ThinkingResponse.model_validate(created.thinking)

        return StrategyResponse(
            id=created.id,
            name=created.name,
            title=created.title,
            description=description,
            siteId=created.site_id,
            recordType=created.record_type,
            steps=steps_responses,
            rootStepId=ast.root.id,
            wdkStrategyId=created.wdk_strategy_id,
            messages=messages_list,
            thinking=thinking_obj,
            createdAt=created.created_at,
            updatedAt=created.updated_at,
        )
    except AppError:
        raise
    except WDKError as e:
        # Preserve upstream status/detail for debugging (e.g. permission denied).
        logger.error("WDK import failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK import failed", error=str(e))
        raise WDKError(f"Failed to import strategy from WDK: {e}") from e


@router.post("/{strategyId:uuid}/push", response_model=PushResultResponse)
async def push_to_wdk(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
) -> PushResultResponse:
    """Push strategy to VEuPathDB WDK."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    try:
        plan = strategy.plan if isinstance(strategy.plan, dict) else {}
        strategy_ast = validate_plan_or_raise(plan)

        api = get_strategy_api(strategy.site_id)

        await _validate_transform_steps_accept_input(strategy_ast=strategy_ast, api=api)

        result = await compile_strategy(strategy_ast, api, site_id=strategy.site_id)

        wdk_strategy_id: int
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
            wdk_strategy_id_raw: int | None = None
            if isinstance(wdk_result, dict):
                strategy_id_raw = wdk_result.get("strategyId")
                id_raw = wdk_result.get("id")
                if isinstance(strategy_id_raw, int):
                    wdk_strategy_id_raw = strategy_id_raw
                elif isinstance(id_raw, int):
                    wdk_strategy_id_raw = id_raw
            if wdk_strategy_id_raw is None:
                raise WDKError("Failed to create strategy: no strategy ID returned")
            wdk_strategy_id = wdk_strategy_id_raw

        compiled_map = {s.local_id: s.wdk_step_id for s in result.steps}
        # Pull step counts from the strategy payload. Calling
        # /steps/{id}/reports/standard can fail for detached steps (422).
        wdk_strategy: JSONObject | None = None
        if wdk_strategy_id is not None:
            try:
                wdk_strategy = await api.get_strategy(wdk_strategy_id)
            except Exception:
                wdk_strategy = None

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

        # Rewrite local ids to WDK ids in the persisted plan.
        for step in strategy_ast.get_all_steps():
            wdk_step_id = compiled_map.get(step.id)
            if wdk_step_id:
                step.id = str(wdk_step_id)

        await strategy_repo.update(
            strategy_id=strategyId,
            wdk_strategy_id=wdk_strategy_id,
            wdk_strategy_id_set=True,
            plan=strategy_ast.to_dict(),
            record_type=strategy_ast.record_type,
        )

        site = get_site(strategy.site_id)
        # Prefer the rootStepId from the persisted WDK strategy payload; when a strategy
        # update fails (or is ignored), `result.root_step_id` refers to a detached step.
        root_step_id: int | None = None
        if isinstance(wdk_strategy, dict):
            root_step_id_raw = wdk_strategy.get("rootStepId") or wdk_strategy.get(
                "root_step_id"
            )
            if isinstance(root_step_id_raw, int):
                root_step_id = root_step_id_raw
            elif isinstance(root_step_id_raw, str) and root_step_id_raw.isdigit():
                root_step_id = int(root_step_id_raw)
        final_root_step_id: int | None = root_step_id or result.root_step_id
        wdk_url = site.strategy_url(wdk_strategy_id, final_root_step_id)

        return PushResultResponse(
            wdkStrategyId=wdk_strategy_id,
            wdkUrl=wdk_url,
        )

    except AppError:
        raise
    except Exception as e:
        logger.error("Push to WDK failed", error=str(e))
        raise WDKError(f"WDK error: {e}") from e


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

        record_type_fallback: str = strategy.record_type or "gene"
        ast, steps_data = _build_snapshot_from_wdk(
            wdk_strategy, record_type_fallback=record_type_fallback
        )
        await _normalize_synced_parameters(ast, steps_data, api)
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)
        ast.name = ast.name or strategy.name

        updated = await strategy_repo.update(
            strategy_id=strategyId,
            name=ast.name or strategy.name,
            plan=ast.to_dict(),
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )

        plan_dict: JSONObject = updated.plan if isinstance(updated.plan, dict) else {}
        metadata_raw = plan_dict.get("metadata")
        metadata: JSONObject = metadata_raw if isinstance(metadata_raw, dict) else {}
        description_raw = metadata.get("description")
        description: str | None = (
            description_raw if isinstance(description_raw, str) else None
        )

        steps_responses: list[StepResponse] = []
        for s in steps_data:
            if isinstance(s, dict):
                steps_responses.append(build_step_response(s))

        return StrategyResponse(
            id=updated.id,
            name=updated.name,
            description=description,
            siteId=updated.site_id,
            recordType=updated.record_type,
            steps=steps_responses,
            rootStepId=ast.root.id,
            wdkStrategyId=updated.wdk_strategy_id,
            createdAt=updated.created_at,
            updatedAt=updated.updated_at,
        )
    except AppError:
        raise
    except WDKError as e:
        logger.error("WDK sync failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK sync failed", error=str(e))
        raise WDKError(f"Failed to sync strategy from WDK: {e}") from e
