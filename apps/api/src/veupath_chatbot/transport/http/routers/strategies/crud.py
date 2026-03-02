"""Local strategy CRUD endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.auto_push import try_auto_push_to_wdk
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.schemas import (
    CreateStrategyRequest,
    StrategyResponse,
    StrategySummaryResponse,
    UpdateStrategyRequest,
)

from ._shared import (
    build_strategy_response,
    build_summary_response,
    extract_root_step_id,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.get("", response_model=list[StrategySummaryResponse])
async def list_strategies(
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[StrategySummaryResponse]:
    """List user's saved strategies."""
    strategies = await strategy_repo.list_by_user(user_id, site_id)
    return [build_summary_response(s) for s in strategies]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    request: CreateStrategyRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Create a new strategy."""
    plan_in = request.plan.model_dump(exclude_none=True)
    strategy_ast = validate_plan_or_raise(plan_in)
    plan = strategy_ast.to_dict()
    steps_data = build_steps_data_from_plan(plan)

    strategy = await strategy_repo.create(
        user_id=user_id,
        name=request.name,
        title=request.name,
        site_id=request.site_id,
        record_type=strategy_ast.record_type,
        plan=plan,
    )

    return build_strategy_response(
        strategy,
        plan=plan,
        steps_data=steps_data,
        root_step_id=strategy_ast.root.id,
    )


@router.get("/{strategyId:uuid}", response_model=StrategyResponse)
async def get_strategy(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
) -> StrategyResponse:
    """Get a strategy by ID."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    plan: JSONObject = strategy.plan if isinstance(strategy.plan, dict) else {}
    steps = build_steps_data_from_plan(plan)
    if not steps and strategy.steps:
        steps = strategy.steps if isinstance(strategy.steps, list) else []

    root_step_id = extract_root_step_id(plan, strategy.root_step_id)

    return build_strategy_response(
        strategy,
        plan=plan,
        steps_data=steps,
        root_step_id=root_step_id,
    )


@router.patch("/{strategyId:uuid}", response_model=StrategyResponse)
async def update_strategy(
    strategyId: UUID,
    request: UpdateStrategyRequest,
    strategy_repo: StrategyRepo,
) -> StrategyResponse:
    """Update a strategy."""
    record_type = None
    if request.plan:
        plan_in = request.plan.model_dump(exclude_none=True)
        strategy_ast = validate_plan_or_raise(plan_in)
        plan = strategy_ast.to_dict()
        record_type = strategy_ast.record_type
    else:
        plan = None

    fields_set: set[str] = getattr(request, "model_fields_set", set())
    wdk_strategy_id_set = "wdk_strategy_id" in fields_set
    is_saved_set = "is_saved" in fields_set

    strategy = await strategy_repo.update(
        strategy_id=strategyId,
        name=request.name,
        title=request.name,
        plan=plan,
        record_type=record_type,
        wdk_strategy_id=request.wdk_strategy_id,
        wdk_strategy_id_set=wdk_strategy_id_set,
        is_saved=request.is_saved,
        is_saved_set=is_saved_set,
    )
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    await strategy_repo.refresh(strategy)

    plan_obj: JSONObject = strategy.plan if isinstance(strategy.plan, dict) else {}
    steps = build_steps_data_from_plan(plan_obj)
    root_step_id = extract_root_step_id(plan_obj, None)

    # If isSaved was toggled and WDK strategy exists, sync the flag to WDK.
    if is_saved_set and strategy.wdk_strategy_id:
        try:
            api = get_strategy_api(strategy.site_id)
            await api.set_saved(strategy.wdk_strategy_id, strategy.is_saved)
        except Exception as e:
            logger.warning(
                "Failed to sync isSaved to WDK",
                strategy_id=str(strategyId),
                error=str(e),
            )

    # Best-effort auto-push to WDK (fire-and-forget).
    if strategy.wdk_strategy_id and not is_saved_set:
        asyncio.create_task(try_auto_push_to_wdk(strategyId))

    return build_strategy_response(
        strategy,
        plan=plan_obj,
        steps_data=steps,
        root_step_id=root_step_id,
    )


@router.delete("/{strategyId:uuid}", status_code=204, response_class=Response)
async def delete_strategy(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
) -> Response:
    """Delete a strategy."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    if strategy.wdk_strategy_id:
        try:
            api = get_strategy_api(strategy.site_id)
            await api.delete_strategy(strategy.wdk_strategy_id)
        except Exception as e:
            logger.warning(
                "WDK strategy delete skipped",
                wdk_strategy_id=strategy.wdk_strategy_id,
                site_id=strategy.site_id,
                error=str(e),
            )

    deleted = await strategy_repo.delete(strategyId)
    if not deleted:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return Response(status_code=204)
