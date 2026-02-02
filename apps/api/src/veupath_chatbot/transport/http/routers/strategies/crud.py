"""Local strategy CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.transport.http.schemas import (
    CreateStrategyRequest,
    StrategyResponse,
    StrategySummaryResponse,
    UpdateStrategyRequest,
)

from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.step_builders import _step_identity_key
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
    _build_snapshot_from_wdk,
)

from ._shared import build_step_response

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.get("", response_model=list[StrategySummaryResponse])
async def list_strategies(
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
):
    """List user's saved strategies."""
    strategies = await strategy_repo.list_by_user(user_id, site_id)
    return [
        StrategySummaryResponse(
            id=s.id,
            name=s.name,
            title=s.title,
            siteId=s.site_id,
            recordType=s.record_type,
            stepCount=len(s.steps),
            resultCount=s.result_count,
            wdkStrategyId=s.wdk_strategy_id,
            createdAt=s.created_at or datetime.now(timezone.utc),
            updatedAt=s.updated_at or s.created_at or datetime.now(timezone.utc),
        )
        for s in strategies
    ]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    request: CreateStrategyRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
):
    """Create a new strategy."""
    plan = request.plan.model_dump(exclude_none=True)
    strategy_ast = validate_plan_or_raise(plan)

    steps_data = build_steps_data_from_plan(plan)

    strategy = await strategy_repo.create(
        user_id=user_id,
        name=request.name,
        title=request.name,
        site_id=request.site_id,
        record_type=strategy_ast.record_type,
        plan=plan,
        steps=steps_data,
        root_step_id=strategy_ast.root.id,
    )

    strategy_data = strategy.__dict__
    plan = strategy_data.get("plan") or {}
    steps = strategy_data.get("steps") or []
    description = (
        plan.get("metadata", {}).get("description") if isinstance(plan, dict) else None
    )
    created_at = strategy_data.get("created_at") or datetime.now(timezone.utc)
    updated_at = strategy_data.get("updated_at") or created_at
    return StrategyResponse(
        id=strategy_data.get("id") or strategy.id,
        name=strategy_data.get("name") or strategy.name,
        title=strategy_data.get("title") or strategy.title,
        description=description,
        siteId=strategy_data.get("site_id") or strategy.site_id,
        recordType=strategy_data.get("record_type") or strategy.record_type,
        steps=[build_step_response(s) for s in steps],
        rootStepId=strategy_data.get("root_step_id"),
        wdkStrategyId=strategy_data.get("wdk_strategy_id"),
        messages=strategy_data.get("messages") or strategy.messages,
        thinking=strategy_data.get("thinking") or strategy.thinking,
        createdAt=created_at,
        updatedAt=updated_at,
    )


@router.get("/{strategyId:uuid}", response_model=StrategyResponse)
async def get_strategy(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
):
    """Get a strategy by ID."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")

    description = (
        (strategy.plan or {}).get("metadata", {}).get("description")
        if isinstance(strategy.plan, dict)
        else None
    )
    steps = list(strategy.steps or [])
    if strategy.wdk_strategy_id and steps:
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_strategy = await api.get_strategy(strategy.wdk_strategy_id)
            _attach_counts_from_wdk_strategy(steps, wdk_strategy)
            if not any(isinstance(step.get("resultCount"), int) for step in steps):
                _, wdk_steps = _build_snapshot_from_wdk(
                    wdk_strategy, record_type_fallback=strategy.record_type or "gene"
                )
                wdk_by_key: dict[
                    tuple[str, str, str, str, str], list[dict[str, Any]]
                ] = {}
                for wdk_step in wdk_steps:
                    wdk_by_key.setdefault(_step_identity_key(wdk_step), []).append(wdk_step)
                for step in steps:
                    match_list = wdk_by_key.get(_step_identity_key(step))
                    if not match_list:
                        continue
                    wdk_step = match_list.pop(0)
                    if (
                        step.get("resultCount") is None
                        and wdk_step.get("resultCount") is not None
                    ):
                        step["resultCount"] = wdk_step.get("resultCount")
                    if not step.get("wdkStepId") and wdk_step.get("wdkStepId"):
                        step["wdkStepId"] = wdk_step.get("wdkStepId")
        except Exception as e:
            logger.warning("WDK count refresh skipped", error=str(e))
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        description=description,
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        steps=[build_step_response(s) for s in steps],
        rootStepId=strategy.root_step_id,
        wdkStrategyId=strategy.wdk_strategy_id,
        messages=strategy.messages,
        thinking=strategy.thinking,
        createdAt=strategy.created_at or datetime.now(timezone.utc),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(timezone.utc),
    )


@router.patch("/{strategyId:uuid}", response_model=StrategyResponse)
async def update_strategy(
    strategyId: UUID,
    request: UpdateStrategyRequest,
    strategy_repo: StrategyRepo,
):
    """Update a strategy."""
    steps_data = None
    root_step_id = None
    record_type = None
    if request.plan:
        plan = request.plan.model_dump(exclude_none=True)
        strategy_ast = validate_plan_or_raise(plan)
        steps_data = build_steps_data_from_plan(plan)
        root_step_id = strategy_ast.root.id
        record_type = strategy_ast.record_type
    else:
        plan = None

    fields_set = getattr(request, "model_fields_set", set())
    wdk_strategy_id_set = "wdk_strategy_id" in fields_set

    strategy = await strategy_repo.update(
        strategy_id=strategyId,
        name=request.name,
        title=request.name,
        plan=plan,
        steps=steps_data,
        root_step_id=root_step_id,
        record_type=record_type,
        wdk_strategy_id=request.wdk_strategy_id,
        wdk_strategy_id_set=wdk_strategy_id_set,
    )
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
    await strategy_repo.refresh(strategy)

    description = (
        (strategy.plan or {}).get("metadata", {}).get("description")
        if isinstance(strategy.plan, dict)
        else None
    )
    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        description=description,
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        steps=[build_step_response(s) for s in strategy.steps],
        rootStepId=strategy.root_step_id,
        wdkStrategyId=strategy.wdk_strategy_id,
        messages=strategy.messages,
        thinking=strategy.thinking,
        createdAt=strategy.created_at or datetime.now(timezone.utc),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(timezone.utc),
    )


@router.delete("/{strategyId:uuid}", status_code=204)
async def delete_strategy(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
):
    """Delete a strategy."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")

    if strategy.wdk_strategy_id:
        try:
            api = get_strategy_api(strategy.site_id)
            await api.delete_strategy(strategy.wdk_strategy_id)
        except Exception as e:
            logger.warning("WDK strategy delete skipped", error=str(e))

    deleted = await strategy_repo.delete(strategyId)
    if not deleted:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
    return Response(status_code=204)

