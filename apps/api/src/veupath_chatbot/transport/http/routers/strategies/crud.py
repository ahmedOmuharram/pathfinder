"""Local strategy CRUD endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.auto_push import try_auto_push_to_wdk
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.serialization import (
    build_steps_data_from_plan,
    count_steps_in_plan,
)
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
)
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.schemas import (
    CreateStrategyRequest,
    MessageResponse,
    StrategyResponse,
    StrategySummaryResponse,
    ThinkingResponse,
    UpdateStrategyRequest,
)

from ._shared import build_step_response

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
    return [
        StrategySummaryResponse(
            id=s.id,
            name=s.name,
            title=s.title,
            siteId=s.site_id,
            recordType=s.record_type,
            stepCount=(
                count_steps_in_plan(s.plan or {})
                or (len(s.steps or []) if s.steps else 0)
            ),
            resultCount=s.result_count,
            wdkStrategyId=s.wdk_strategy_id,
            isSaved=s.is_saved,
            createdAt=s.created_at or datetime.now(UTC),
            updatedAt=s.updated_at or s.created_at or datetime.now(UTC),
        )
        for s in strategies
    ]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    request: CreateStrategyRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Create a new strategy."""
    plan_in = request.plan.model_dump(exclude_none=True)
    strategy_ast = validate_plan_or_raise(plan_in)
    # Persist canonical plan (ensures all nodes have ids, and keeps metadata).
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

    strategy_data = strategy.__dict__
    steps = steps_data

    description: str | None = None
    if isinstance(plan, dict):
        metadata_raw = plan.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        desc_raw = metadata.get("description")
        description = desc_raw if isinstance(desc_raw, str) else None

    created_at = strategy_data.get("created_at") or datetime.now(UTC)
    updated_at = strategy_data.get("updated_at") or created_at

    # Convert messages and thinking
    messages: list[MessageResponse] | None = None
    messages_raw = strategy_data.get("messages") or strategy.messages
    if isinstance(messages_raw, list) and messages_raw:
        try:
            parsed_messages: list[MessageResponse] = []
            for msg in messages_raw:
                parsed_messages.append(MessageResponse.model_validate(msg))
            messages = parsed_messages
        except Exception:
            messages = None

    thinking: ThinkingResponse | None = None
    thinking_raw = strategy_data.get("thinking") or strategy.thinking
    if isinstance(thinking_raw, dict) and thinking_raw:
        try:
            thinking = ThinkingResponse.model_validate(thinking_raw)
        except Exception:
            thinking = None

    return StrategyResponse(
        id=strategy_data.get("id") or strategy.id,
        name=strategy_data.get("name") or strategy.name,
        title=strategy_data.get("title") or strategy.title,
        description=description,
        siteId=strategy_data.get("site_id") or strategy.site_id,
        recordType=strategy_data.get("record_type") or strategy.record_type,
        steps=[build_step_response(s) for s in steps if isinstance(s, dict)],
        rootStepId=strategy_ast.root.id,
        wdkStrategyId=strategy_data.get("wdk_strategy_id"),
        isSaved=strategy.is_saved,
        messages=messages,
        thinking=thinking,
        modelId=strategy.model_id,
        createdAt=created_at,
        updatedAt=updated_at,
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

    description: str | None = None
    if isinstance(plan, dict):
        metadata_raw = plan.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        desc_raw = metadata.get("description")
        description = desc_raw if isinstance(desc_raw, str) else None

    steps = build_steps_data_from_plan(plan)
    if not steps and strategy.steps:
        steps = strategy.steps if isinstance(strategy.steps, list) else []

    root_step_id: str | None = None
    if isinstance(plan, dict):
        root_raw = plan.get("root")
        root = root_raw if isinstance(root_raw, dict) else {}
        root_id_raw = root.get("id")
        root_step_id = root_id_raw if isinstance(root_id_raw, str) else None
    if not root_step_id and strategy.root_step_id:
        root_step_id = strategy.root_step_id

    if strategy.wdk_strategy_id and steps:
        try:
            api = get_strategy_api(strategy.site_id)
            wdk_strategy = await api.get_strategy(strategy.wdk_strategy_id)
            _attach_counts_from_wdk_strategy(steps, wdk_strategy)
        except Exception as e:
            logger.warning("WDK count refresh skipped", error=str(e))

    # Convert messages and thinking
    messages: list[MessageResponse] | None = None
    if isinstance(strategy.messages, list) and strategy.messages:
        try:
            parsed_messages: list[MessageResponse] = []
            for msg in strategy.messages:
                parsed_messages.append(MessageResponse.model_validate(msg))
            messages = parsed_messages
        except Exception:
            messages = None

    thinking: ThinkingResponse | None = None
    if isinstance(strategy.thinking, dict) and strategy.thinking:
        try:
            thinking = ThinkingResponse.model_validate(strategy.thinking)
        except Exception:
            thinking = None

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        description=description,
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        steps=[build_step_response(s) for s in steps if isinstance(s, dict)],
        rootStepId=root_step_id,
        wdkStrategyId=strategy.wdk_strategy_id,
        isSaved=strategy.is_saved,
        messages=messages,
        thinking=thinking,
        modelId=strategy.model_id,
        createdAt=strategy.created_at or datetime.now(UTC),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(UTC),
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
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    await strategy_repo.refresh(strategy)

    plan_obj: JSONObject = strategy.plan if isinstance(strategy.plan, dict) else {}
    description: str | None = None
    if isinstance(plan_obj, dict):
        metadata_raw = plan_obj.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        desc_raw = metadata.get("description")
        description = desc_raw if isinstance(desc_raw, str) else None
    steps = build_steps_data_from_plan(plan_obj)

    root_step_id: str | None = None
    if isinstance(plan_obj, dict):
        root_raw = plan_obj.get("root")
        root = root_raw if isinstance(root_raw, dict) else {}
        root_id_raw = root.get("id")
        root_step_id = root_id_raw if isinstance(root_id_raw, str) else None

    # Convert messages and thinking
    messages: list[MessageResponse] | None = None
    if isinstance(strategy.messages, list) and strategy.messages:
        try:
            parsed_messages: list[MessageResponse] = []
            for msg in strategy.messages:
                parsed_messages.append(MessageResponse.model_validate(msg))
            messages = parsed_messages
        except Exception:
            messages = None

    thinking: ThinkingResponse | None = None
    if isinstance(strategy.thinking, dict) and strategy.thinking:
        try:
            thinking = ThinkingResponse.model_validate(strategy.thinking)
        except Exception:
            thinking = None

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
        asyncio.create_task(try_auto_push_to_wdk(strategyId, strategy_repo))

    return StrategyResponse(
        id=strategy.id,
        name=strategy.name,
        title=strategy.title,
        description=description,
        siteId=strategy.site_id,
        recordType=strategy.record_type,
        steps=[build_step_response(s) for s in steps if isinstance(s, dict)],
        rootStepId=root_step_id,
        wdkStrategyId=strategy.wdk_strategy_id,
        isSaved=strategy.is_saved,
        messages=messages,
        thinking=thinking,
        modelId=strategy.model_id,
        createdAt=strategy.created_at or datetime.now(UTC),
        updatedAt=strategy.updated_at or strategy.created_at or datetime.now(UTC),
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
            logger.warning("WDK strategy delete skipped", error=str(e))

    deleted = await strategy_repo.delete(strategyId)
    if not deleted:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return Response(status_code=204)
