"""Step analysis endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.domain.strategy.ast import StepAnalysis
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, as_json_object
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.routers.steps._shared import (
    find_step,
    get_steps_as_objects,
    update_plan,
)
from veupath_chatbot.transport.http.schemas import (
    StepAnalysisRequest,
    StepAnalysisResponse,
    StepAnalysisRunResponse,
)

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])
logger = get_logger(__name__)


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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    updated_plan = update_plan(
        plan, step_id, {"analyses": [a.to_dict() for a in analyses]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    wdk_result: JSONObject | None = None
    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = get_steps_as_objects(updated_steps_raw)
    updated_step = find_step(updated_steps, step_id) or step
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
