"""Step-level operations (filters, analyses, reports)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
    from_dict,
)
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.schemas import (
    StepAnalysisRequest,
    StepAnalysisRunResponse,
    StepFilterRequest,
    StepFiltersResponse,
    StepReportRequest,
    StepReportRunResponse,
    StepResponse,
    StepFilterResponse,
)
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])
logger = get_logger(__name__)


def _find_step(strategy_steps: list[dict[str, Any]], step_id: str) -> dict[str, Any] | None:
    for step in strategy_steps:
        if step.get("id") == step_id:
            return step
    return None


def _update_plan(
    plan: dict[str, Any], step_id: str, updates: dict[str, Any]
) -> dict[str, Any]:
    """Update a plan AST with step attachments."""
    try:
        ast = from_dict(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        )

    step = ast.get_step_by_id(step_id)
    if not step:
        return plan

    if "filters" in updates:
        step.filters = updates["filters"]
    if "analyses" in updates:
        step.analyses = updates["analyses"]
    if "reports" in updates:
        step.reports = updates["reports"]
    return ast.to_dict()


@router.get("/{step_id}", response_model=StepResponse)
async def get_step(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Get a step from a strategy."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    return StepResponse(**step)


@router.get("/{step_id}/filters", response_model=list[StepFilterResponse])
async def list_step_filters(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """List filters attached to a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    return step.get("filters", []) or []


@router.get("/{step_id}/filters/available", response_model=list[dict[str, Any]])
async def list_available_filters(strategyId: UUID, step_id: str, strategy_repo: StrategyRepo, user_id: CurrentUser):
    """List available filters for a step (WDK-backed)."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step or not step.get("wdkStepId"):
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
    return await api.list_step_filters(step["wdkStepId"])


@router.put("/{step_id}/filters/{filter_name}", response_model=StepFiltersResponse)
async def set_step_filter(
    strategyId: UUID,
    step_id: str,
    filter_name: str,
    request: StepFilterRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Add or update a filter for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    filters = [
        StepFilter(
            name=str(f.get("name")),
            value=f.get("value"),
            disabled=bool(f.get("disabled", False)),
        )
        for f in (step.get("filters") or [])
        if isinstance(f, dict) and f.get("name") is not None
    ]
    filters = [f for f in filters if f.name != filter_name]
    filters.append(StepFilter(name=filter_name, value=request.value, disabled=request.disabled))

    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(plan, step_id, {"filters": filters})
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps = build_steps_data_from_plan(updated_plan)
    updated_step = _find_step(updated_steps, step_id) or step
    if updated_step.get("wdkStepId"):
        try:
            api = get_strategy_api(strategy.site_id)
            await api.set_step_filter(
                step_id=updated_step["wdkStepId"],
                filter_name=filter_name,
                value=request.value,
                disabled=request.disabled,
            )
        except Exception as e:
            logger.warning("WDK filter update failed", error=str(e))

    return StepFiltersResponse(filters=[f.to_dict() for f in filters])


@router.delete("/{step_id}/filters/{filter_name}", response_model=StepFiltersResponse)
async def delete_step_filter(
    strategyId: UUID,
    step_id: str,
    filter_name: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Remove a filter from a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    filters = [
        StepFilter(
            name=str(f.get("name")),
            value=f.get("value"),
            disabled=bool(f.get("disabled", False)),
        )
        for f in (step.get("filters") or [])
        if isinstance(f, dict) and f.get("name") != filter_name
    ]
    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(plan, step_id, {"filters": filters})
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps = build_steps_data_from_plan(updated_plan)
    updated_step = _find_step(updated_steps, step_id) or step
    if updated_step.get("wdkStepId"):
        try:
            api = get_strategy_api(strategy.site_id)
            await api.delete_step_filter(step_id=updated_step["wdkStepId"], filter_name=filter_name)
        except Exception as e:
            logger.warning("WDK filter delete failed", error=str(e))

    return StepFiltersResponse(filters=[f.to_dict() for f in filters])


@router.get("/{step_id}/analysis-types", response_model=list[dict[str, Any]])
async def list_analysis_types(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """List available analysis types for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step or not step.get("wdkStepId"):
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
    return await api.list_analysis_types(step["wdkStepId"])


@router.get("/{step_id}/analysis-types/{analysis_type}", response_model=dict[str, Any])
async def get_analysis_type(
    strategyId: UUID,
    step_id: str,
    analysis_type: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Get analysis form metadata for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step or not step.get("wdkStepId"):
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
    return await api.get_analysis_type(step["wdkStepId"], analysis_type)


@router.get("/{step_id}/analyses", response_model=list[dict[str, Any]])
async def list_step_analyses(strategyId: UUID, step_id: str, strategy_repo: StrategyRepo, user_id: CurrentUser):
    """List analysis instances for a step."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step or not step.get("wdkStepId"):
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
    return await api.list_step_analyses(step["wdkStepId"])


@router.post("/{step_id}/analyses", response_model=StepAnalysisRunResponse)
async def run_step_analysis(
    strategyId: UUID,
    step_id: str,
    request: StepAnalysisRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Run a step analysis and attach it locally."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    analyses = [
        StepAnalysis(
            analysis_type=str(a.get("analysisType") or a.get("analysis_type")),
            parameters=a.get("parameters") or {},
            custom_name=a.get("customName") or a.get("custom_name"),
        )
        for a in (step.get("analyses") or [])
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
    updated_plan = _update_plan(plan, step_id, {"analyses": analyses})
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    wdk_result = None
    updated_steps = build_steps_data_from_plan(updated_plan)
    updated_step = _find_step(updated_steps, step_id) or step
    if updated_step.get("wdkStepId"):
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_result = await api.run_step_analysis(
                step_id=updated_step["wdkStepId"],
                analysis_type=request.analysis_type,
                parameters=request.parameters,
                custom_name=request.custom_name,
            )
        except Exception as e:
            logger.warning("WDK analysis failed", error=str(e))

    return StepAnalysisRunResponse(analysis=analyses[-1].to_dict(), wdk=wdk_result)


@router.post("/{step_id}/reports", response_model=StepReportRunResponse)
async def run_step_report(
    strategyId: UUID,
    step_id: str,
    request: StepReportRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Run a report and attach it locally."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps = build_steps_data_from_plan(strategy.plan or {})
    step = _find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    reports = [
        StepReport(
            report_name=str(r.get("reportName") or r.get("report_name") or "standard"),
            config=r.get("config") or {},
        )
        for r in (step.get("reports") or [])
        if isinstance(r, dict)
    ]
    reports.append(StepReport(report_name=request.report_name, config=request.config))

    plan = strategy.plan if isinstance(strategy.plan, dict) else {}
    updated_plan = _update_plan(plan, step_id, {"reports": reports})
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    wdk_result = None
    updated_steps = build_steps_data_from_plan(updated_plan)
    updated_step = _find_step(updated_steps, step_id) or step
    if updated_step.get("wdkStepId"):
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_result = await api.run_step_report(
                step_id=updated_step["wdkStepId"],
                report_name=request.report_name,
                config=request.config,
            )
        except Exception as e:
            logger.warning("WDK report failed", error=str(e))

    return StepReportRunResponse(report=reports[-1].to_dict(), wdk=wdk_result)

