"""Strategy CRUD endpoints — CQRS only (streams + stream_projections)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.persistence.repositories.stream import ProjectionUpdate
from veupath_chatbot.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.platform.events import read_stream_messages, read_stream_thinking
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.orchestrator import cancel_chat_operation
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.wdk_sync import (
    lazy_fetch_wdk_detail,
    sync_is_saved_to_wdk,
)
from veupath_chatbot.services.wdk import get_strategy_api
from veupath_chatbot.transport.http.deps import CurrentUser, StreamRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_projection_or_404
from veupath_chatbot.transport.http.schemas import (
    CreateStrategyRequest,
    StrategyResponse,
    UpdateStrategyRequest,
)

from ._shared import (
    build_projection_response,
    build_projection_summary,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    stream_repo: StreamRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[StrategyResponse]:
    """List user's conversation streams (projections)."""
    projections = await stream_repo.list_projections(user_id, site_id)
    return [build_projection_summary(p, site_id=site_id or "") for p in projections]


@router.get("/dismissed", response_model=list[StrategyResponse])
async def list_dismissed_strategies(
    stream_repo: StreamRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[StrategyResponse]:
    """List user's dismissed (soft-deleted) strategies."""
    projections = await stream_repo.list_dismissed_projections(user_id, site_id)
    return [build_projection_summary(p, site_id=site_id or "") for p in projections]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    request: CreateStrategyRequest,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Create a new strategy (CQRS only)."""
    plan_in = request.plan.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan_in)
    plan = payload.model_dump(by_alias=True, exclude_none=True, mode="json")

    stream = await stream_repo.create(
        user_id=user_id,
        site_id=request.site_id,
        name=request.name,
    )
    await stream_repo.update_projection(
        stream.id,
        ProjectionUpdate(
            plan=plan,
            record_type=payload.record_type,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )

    projection = await stream_repo.get_projection(stream.id)
    if not projection:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_projection_response(projection)


@router.get("/{strategyId:uuid}", response_model=StrategyResponse)
async def get_strategy(
    strategyId: UUID,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Get a strategy/stream by ID from the CQRS projection + Redis."""
    projection = await get_owned_projection_or_404(stream_repo, strategyId, user_id)

    # Lazy detail fetch: if this is a WDK-linked strategy with no plan data,
    # fetch the full detail from WDK now (summary-only projections are created
    # during sync-wdk to avoid the N+1 problem).
    projection = await lazy_fetch_wdk_detail(
        projection=projection,
        stream_repo=stream_repo,
    )

    redis = get_redis()
    messages = await read_stream_messages(redis, str(strategyId))
    thinking = await read_stream_thinking(redis, str(strategyId))
    return build_projection_response(projection, messages=messages, thinking=thinking)


@router.patch("/{strategyId:uuid}", response_model=StrategyResponse)
async def update_strategy(
    strategyId: UUID,
    request: UpdateStrategyRequest,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Update a strategy (CQRS only)."""
    await get_owned_projection_or_404(stream_repo, strategyId, user_id)

    payload = None
    record_type = None
    plan: JSONObject | None = None
    if request.plan:
        plan_in = request.plan.model_dump(exclude_none=True)
        payload = validate_plan_or_raise(plan_in)
        plan = payload.model_dump(by_alias=True, exclude_none=True, mode="json")
        record_type = payload.record_type

    fields_set: set[str] = getattr(request, "model_fields_set", set())
    wdk_strategy_id_set = "wdk_strategy_id" in fields_set
    is_saved_set = "is_saved" in fields_set

    await stream_repo.update_projection(
        strategyId,
        ProjectionUpdate(
            name=request.name,
            plan=plan,
            record_type=record_type,
            wdk_strategy_id=request.wdk_strategy_id,
            wdk_strategy_id_set=wdk_strategy_id_set,
            is_saved=request.is_saved,
            is_saved_set=is_saved_set,
            step_count=len(walk_step_tree(payload.root)) if payload else None,
        ),
    )

    # Re-fetch updated projection.
    updated = await stream_repo.get_projection(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    # If isSaved was toggled and WDK strategy exists, sync the flag to WDK.
    if is_saved_set and updated.wdk_strategy_id:
        await sync_is_saved_to_wdk(projection=updated)

    return build_projection_response(updated)


@router.delete("/{strategyId:uuid}", status_code=204, response_class=Response)
async def delete_strategy(
    strategyId: UUID,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
    *,
    delete_from_wdk: Annotated[bool, Query(alias="deleteFromWdk")] = False,
) -> Response:
    """Delete a strategy: cancel ops, clean Redis stream, delete CQRS records.

    For WDK-linked strategies with ``deleteFromWdk=false`` (default), the
    strategy is soft-deleted (dismissed) instead of hard-deleted. This prevents
    WDK sync from re-importing it. Use the restore endpoint to un-dismiss.

    Pass ``deleteFromWdk=true`` to hard-delete from both PathFinder and WDK.
    Non-WDK strategies are always hard-deleted.
    """
    projection = await get_owned_projection_or_404(stream_repo, strategyId, user_id)

    active_ops = await stream_repo.get_active_operations(strategyId)
    for op in active_ops:
        await cancel_chat_operation(op.operation_id)

    # Clean up Redis stream.
    redis = get_redis()
    await redis.delete(f"stream:{strategyId}")

    is_wdk_linked = projection.wdk_strategy_id is not None

    if is_wdk_linked and not delete_from_wdk:
        # Soft-delete: dismiss the projection (hidden from list, skipped by sync).
        await stream_repo.dismiss(strategyId)
    else:
        # Hard-delete: remove from WDK if requested, then delete CQRS records.
        if delete_from_wdk and projection.wdk_strategy_id and projection.stream:
            try:
                api = get_strategy_api(projection.stream.site_id)
                await api.delete_strategy(projection.wdk_strategy_id)
            except (AppError, OSError, RuntimeError) as e:
                logger.warning(
                    "WDK strategy delete failed",
                    wdk_strategy_id=projection.wdk_strategy_id,
                    error=str(e),
                )
        await stream_repo.delete(strategyId)

    return Response(status_code=204)


@router.get("/{strategyId:uuid}/ast")
async def get_strategy_ast(
    strategyId: UUID,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> JSONObject:
    """Return the raw plan AST from a strategy's projection."""
    projection = await get_owned_projection_or_404(stream_repo, strategyId, user_id)
    plan = projection.plan
    if not plan or not isinstance(plan, dict):
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy has no plan AST",
        )
    return plan


@router.post("/{strategyId:uuid}/restore", response_model=StrategyResponse)
async def restore_strategy(
    strategyId: UUID,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Restore a dismissed (soft-deleted) strategy.

    Clears dismissed_at, resets plan to empty (triggers lazy WDK re-fetch),
    and wipes message history. The strategy reappears as if freshly imported.
    """
    projection = await get_owned_projection_or_404(stream_repo, strategyId, user_id)
    if projection.dismissed_at is None:
        raise ValidationError(
            detail="Strategy is not dismissed",
            errors=[
                {
                    "path": "strategyId",
                    "message": "Not dismissed",
                    "code": "INVALID_STATE",
                }
            ],
        )
    await stream_repo.restore(strategyId)

    # Wipe Redis messages (clean slate).
    redis = get_redis()
    await redis.delete(f"stream:{strategyId}")

    updated = await stream_repo.get_projection(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_projection_summary(updated)
