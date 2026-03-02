"""Step report endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.domain.strategy.ast import StepReport
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, as_json_object
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.routers.steps._shared import (
    find_step,
    get_steps_as_objects,
    update_plan,
)
from veupath_chatbot.transport.http.schemas import (
    StepReportRequest,
    StepReportResponse,
    StepReportRunResponse,
)

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])
logger = get_logger(__name__)


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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    updated_plan = update_plan(
        plan, step_id, {"reports": [r.to_dict() for r in reports]}
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
