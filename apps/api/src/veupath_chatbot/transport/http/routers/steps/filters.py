"""Step filter endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.domain.strategy.ast import StepFilter
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.routers.steps._shared import (
    find_step,
    get_steps_as_objects,
    update_plan,
)
from veupath_chatbot.transport.http.schemas import (
    StepFilterRequest,
    StepFilterResponse,
    StepFiltersResponse,
)

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])
logger = get_logger(__name__)


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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    updated_plan = update_plan(
        plan, step_id, {"filters": [f.to_dict() for f in filters]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = get_steps_as_objects(updated_steps_raw)
    updated_step = find_step(updated_steps, step_id) or step
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
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
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
    updated_plan = update_plan(
        plan, step_id, {"filters": [f.to_dict() for f in filters]}
    )
    await strategy_repo.update(
        strategy_id=strategyId,
        plan=updated_plan,
    )

    updated_steps_raw = build_steps_data_from_plan(updated_plan)
    updated_steps = get_steps_as_objects(updated_steps_raw)
    updated_step = find_step(updated_steps, step_id) or step
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
