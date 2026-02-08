"""Step-level operations (filters, analyses, reports)."""

from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
    from_dict,
)
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, as_json_object
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.schemas import (
    StepAnalysisRequest,
    StepAnalysisResponse,
    StepAnalysisRunResponse,
    StepFilterRequest,
    StepFilterResponse,
    StepFiltersResponse,
    StepReportRequest,
    StepReportResponse,
    StepReportRunResponse,
    StepResponse,
)

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])
logger = get_logger(__name__)


def _get_steps_as_objects(steps: JSONArray) -> list[JSONObject]:
    """Convert JSONArray to list[JSONObject] with type checking."""
    result: list[JSONObject] = []
    for step in steps:
        if isinstance(step, dict):
            result.append(step)
    return result


def _find_step(strategy_steps: list[JSONObject], step_id: str) -> JSONObject | None:
    for step in strategy_steps:
        if step.get("id") == step_id:
            return step
    return None


def _update_plan(plan: JSONObject, step_id: str, updates: JSONObject) -> JSONObject:
    """Update a plan AST with step attachments."""
    try:
        ast = from_dict(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        ) from exc

    step = ast.get_step_by_id(step_id)
    if not step:
        return plan

    if "filters" in updates:
        filters_raw = updates["filters"]
        if isinstance(filters_raw, list):
            step.filters = [
                StepFilter(
                    name=str(f.get("name", "")),
                    value=f.get("value"),
                    disabled=bool(f.get("disabled", False)),
                )
                for f in filters_raw
                if isinstance(f, dict) and f.get("name") is not None
            ]
    if "analyses" in updates:
        analyses_raw = updates["analyses"]
        if isinstance(analyses_raw, list):
            step.analyses = [
                StepAnalysis(
                    analysis_type=str(
                        a.get("analysisType") or a.get("analysis_type", "")
                    ),
                    parameters=as_json_object(a.get("parameters"))
                    if isinstance(a.get("parameters"), dict)
                    else {},
                )
                for a in analyses_raw
                if isinstance(a, dict)
                and (a.get("analysisType") or a.get("analysis_type")) is not None
            ]
    if "reports" in updates:
        reports_raw = updates["reports"]
        if isinstance(reports_raw, list):
            step.reports = [
                StepReport(
                    report_name=str(
                        r.get("reportName") or r.get("report_name", "standard")
                    ),
                    config=as_json_object(r.get("config"))
                    if isinstance(r.get("config"), dict)
                    else {},
                )
                for r in reports_raw
                if isinstance(r, dict)
            ]
    return ast.to_dict()


@router.get("/{step_id}", response_model=StepResponse)
async def get_step(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepResponse:
    """Get a step from a strategy."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    return StepResponse.model_validate(step)


@router.get("/{step_id}/filters", response_model=list[StepFilterResponse])
async def list_step_filters(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> list[StepFilterResponse]:
    """List filters attached to a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    filters_raw = step.get("filters", [])
    if not isinstance(filters_raw, list):
        return []
    return [
        StepFilterResponse.model_validate(f) for f in filters_raw if isinstance(f, dict)
    ]


@router.get("/{step_id}/filters/available", response_model=JSONArray)
async def list_available_filters(
    strategyId: UUID, step_id: str, strategy_repo: StrategyRepo, user_id: CurrentUser
) -> JSONArray:
    """List available filters for a step (WDK-backed)."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    wdk_step_id_raw = step.get("wdkStepId")
    if not isinstance(wdk_step_id_raw, int):
        raise ValidationError(
            detail="WDK step not available",
            errors=[
                {
                    "path": "steps[].wdkStepId",
                    "message": "WDK step not available",
                    "code": "WDK_STEP_NOT_AVAILABLE",
                }
            ],
        )

    api = get_strategy_api(strategy.site_id)
    return await api.list_step_filters(wdk_step_id_raw)


@router.put("/{step_id}/filters/{filter_name}", response_model=StepFiltersResponse)
async def set_step_filter(
    strategyId: UUID,
    step_id: str,
    filter_name: str,
    request: StepFilterRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepFiltersResponse:
    """Add or update a filter for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    filters_raw = step.get("filters")
    filters: list[StepFilter] = []
    if isinstance(filters_raw, list):
        filters = [
            StepFilter(
                name=str(f.get("name", "")),
                value=f.get("value"),
                disabled=bool(f.get("disabled", False)),
            )
            for f in filters_raw
            if isinstance(f, dict) and f.get("name") is not None
        ]
    filters = [f for f in filters if f.name != filter_name]
    filters.append(
        StepFilter(name=filter_name, value=request.value, disabled=request.disabled)
    )

    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(
        plan, step_id, {"filters": [f.to_dict() for f in filters]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = _get_steps_as_objects(updated_steps_raw)
    updated_step = _find_step(updated_steps, step_id) or step
    wdk_step_id_raw = updated_step.get("wdkStepId")
    if isinstance(wdk_step_id_raw, int):
        try:
            api = get_strategy_api(strategy.site_id)
            await api.set_step_filter(
                step_id=wdk_step_id_raw,
                filter_name=filter_name,
                value=request.value,
                disabled=request.disabled,
            )
        except Exception as e:
            logger.warning("WDK filter update failed", error=str(e))

    return StepFiltersResponse(
        filters=[StepFilterResponse.model_validate(f.to_dict()) for f in filters]
    )


@router.delete("/{step_id}/filters/{filter_name}", response_model=StepFiltersResponse)
async def delete_step_filter(
    strategyId: UUID,
    step_id: str,
    filter_name: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepFiltersResponse:
    """Remove a filter from a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    filters_raw = step.get("filters")
    filters: list[StepFilter] = []
    if isinstance(filters_raw, list):
        filters = [
            StepFilter(
                name=str(f.get("name", "")),
                value=f.get("value"),
                disabled=bool(f.get("disabled", False)),
            )
            for f in filters_raw
            if isinstance(f, dict) and f.get("name") != filter_name
        ]
    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(
        plan, step_id, {"filters": [f.to_dict() for f in filters]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = _get_steps_as_objects(updated_steps_raw)
    updated_step = _find_step(updated_steps, step_id) or step
    wdk_step_id_raw = updated_step.get("wdkStepId")
    if isinstance(wdk_step_id_raw, int):
        try:
            api = get_strategy_api(strategy.site_id)
            await api.delete_step_filter(
                step_id=wdk_step_id_raw, filter_name=filter_name
            )
        except Exception as e:
            logger.warning("WDK filter delete failed", error=str(e))

    return StepFiltersResponse(
        filters=[StepFilterResponse.model_validate(f.to_dict()) for f in filters]
    )


@router.get("/{step_id}/analysis-types", response_model=JSONArray)
async def list_analysis_types(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> JSONArray:
    """List available analysis types for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    wdk_step_id_raw = step.get("wdkStepId")
    if not isinstance(wdk_step_id_raw, int):
        raise ValidationError(
            detail="WDK step not available",
            errors=[
                {
                    "path": "steps[].wdkStepId",
                    "message": "WDK step not available",
                    "code": "WDK_STEP_NOT_AVAILABLE",
                }
            ],
        )
    api = get_strategy_api(strategy.site_id)
    return await api.list_analysis_types(wdk_step_id_raw)


@router.get("/{step_id}/analysis-types/{analysis_type}", response_model=JSONObject)
async def get_analysis_type(
    strategyId: UUID,
    step_id: str,
    analysis_type: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> JSONObject:
    """Get analysis form metadata for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    wdk_step_id_raw = step.get("wdkStepId")
    if not isinstance(wdk_step_id_raw, int):
        raise ValidationError(
            detail="WDK step not available",
            errors=[
                {
                    "path": "steps[].wdkStepId",
                    "message": "WDK step not available",
                    "code": "WDK_STEP_NOT_AVAILABLE",
                }
            ],
        )
    api = get_strategy_api(strategy.site_id)
    return await api.get_analysis_type(wdk_step_id_raw, analysis_type)


@router.get("/{step_id}/analyses", response_model=JSONArray)
async def list_step_analyses(
    strategyId: UUID, step_id: str, strategy_repo: StrategyRepo, user_id: CurrentUser
) -> JSONArray:
    """List analysis instances for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    wdk_step_id_raw = step.get("wdkStepId")
    if not isinstance(wdk_step_id_raw, int):
        raise ValidationError(
            detail="WDK step not available",
            errors=[
                {
                    "path": "steps[].wdkStepId",
                    "message": "WDK step not available",
                    "code": "WDK_STEP_NOT_AVAILABLE",
                }
            ],
        )
    api = get_strategy_api(strategy.site_id)
    return await api.list_step_analyses(wdk_step_id_raw)


@router.post("/{step_id}/analyses", response_model=StepAnalysisRunResponse)
async def run_step_analysis(
    strategyId: UUID,
    step_id: str,
    request: StepAnalysisRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepAnalysisRunResponse:
    """Run a step analysis and attach it locally."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    analyses_raw = step.get("analyses")
    analyses: list[StepAnalysis] = []
    if isinstance(analyses_raw, list):
        analyses = [
            StepAnalysis(
                analysis_type=str(a.get("analysisType") or a.get("analysis_type", "")),
                parameters=as_json_object(a.get("parameters"))
                if isinstance(a.get("parameters"), dict)
                else {},
                custom_name=str(a.get("customName") or a.get("custom_name"))
                if (a.get("customName") or a.get("custom_name")) is not None
                else None,
            )
            for a in analyses_raw
            if isinstance(a, dict) and (a.get("analysisType") or a.get("analysis_type"))
        ]
    analyses.append(
        StepAnalysis(
            analysis_type=request.analysis_type,
            parameters=request.parameters,
            custom_name=request.custom_name,
        )
    )

    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(
        plan, step_id, {"analyses": [a.to_dict() for a in analyses]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    wdk_result: JSONObject | None = None
    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = _get_steps_as_objects(updated_steps_raw)
    updated_step = _find_step(updated_steps, step_id) or step
    wdk_step_id_raw = updated_step.get("wdkStepId")
    if isinstance(wdk_step_id_raw, int):
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_result_raw = await api.run_step_analysis(
                step_id=wdk_step_id_raw,
                analysis_type=request.analysis_type,
                parameters=request.parameters,
                custom_name=request.custom_name,
            )
            wdk_result = wdk_result_raw if isinstance(wdk_result_raw, dict) else None
        except Exception as e:
            logger.warning("WDK analysis failed", error=str(e))

    return StepAnalysisRunResponse(
        analysis=StepAnalysisResponse.model_validate(analyses[-1].to_dict()),
        wdk=wdk_result,
    )


@router.post("/{step_id}/reports", response_model=StepReportRunResponse)
async def run_step_report(
    strategyId: UUID,
    step_id: str,
    request: StepReportRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepReportRunResponse:
    """Run a report and attach it locally."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = _get_steps_as_objects(steps_raw)
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    reports_raw = step.get("reports")
    reports: list[StepReport] = []
    if isinstance(reports_raw, list):
        reports = [
            StepReport(
                report_name=str(
                    r.get("reportName") or r.get("report_name") or "standard"
                ),
                config=as_json_object(r.get("config"))
                if isinstance(r.get("config"), dict)
                else {},
            )
            for r in reports_raw
            if isinstance(r, dict)
        ]
    reports.append(StepReport(report_name=request.report_name, config=request.config))

    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(
        plan, step_id, {"reports": [r.to_dict() for r in reports]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    wdk_result: JSONObject | None = None
    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = _get_steps_as_objects(updated_steps_raw)
    updated_step = _find_step(updated_steps, step_id) or step
    wdk_step_id_raw = updated_step.get("wdkStepId")
    if isinstance(wdk_step_id_raw, int):
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_result_raw = await api.run_step_report(
                step_id=wdk_step_id_raw,
                report_name=request.report_name,
                config=request.config,
            )
            wdk_result = wdk_result_raw if isinstance(wdk_result_raw, dict) else None
        except Exception as e:
            logger.warning("WDK report failed", error=str(e))

    return StepReportRunResponse(
        report=StepReportResponse.model_validate(reports[-1].to_dict()), wdk=wdk_result
    )
