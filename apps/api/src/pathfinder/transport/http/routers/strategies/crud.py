"""Strategy CRUD endpoints.

Backed by the ``chats`` table (one row per conversation with strategy
metadata: name, wdk_strategy_id, plan, step_count, etc.). See
``persistence/models.py`` and ``persistence/repositories/chat.py``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.plan_payload import (
    PersistedStrategyGraph,
    StrategyPlanPayload,
)
from pathfinder.persistence.repositories import ChatUpdate
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_plan_parameters,
)
from pathfinder.services.strategies.plan_validation import validate_plan_or_raise
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.step_wdk_push import push_all_steps_to_wdk
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state
from pathfinder.services.strategies.wdk_sync import (
    lazy_fetch_wdk_detail,
    sync_is_saved_to_wdk,
)
from pathfinder.services.wdk import get_strategy_api
from pathfinder.transport.http.deps import ChatRepo, CurrentUser
from pathfinder.transport.http.routers._authz import get_owned_chat_or_404
from pathfinder.transport.http.schemas import (
    CreateStrategyRequest,
    PushStrategyRequest,
    StrategyResponse,
    UpdateStrategyRequest,
)

from ._shared import (
    build_chat_response,
    build_chat_summary,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    chat_repo: ChatRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[StrategyResponse]:
    """List the user's chats (active, non-dismissed)."""
    chats = await chat_repo.list_chats(user_id, site_id)
    return [build_chat_summary(c, site_id=site_id or "") for c in chats]


@router.get("/dismissed", response_model=list[StrategyResponse])
async def list_dismissed_strategies(
    chat_repo: ChatRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[StrategyResponse]:
    """List the user's dismissed (soft-deleted) chats."""
    chats = await chat_repo.list_dismissed_chats(user_id, site_id)
    return [build_chat_summary(c, site_id=site_id or "") for c in chats]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    request: CreateStrategyRequest,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Create a new strategy (chat with plan metadata)."""
    plan_in = request.plan.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan_in)

    chat = await chat_repo.create(
        user_id=user_id,
        site_id=request.site_id,
        name=request.name,
    )
    await chat_repo.update_chat(
        chat.id,
        ChatUpdate(
            plan=payload,
            record_type=payload.record_type,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )

    refreshed = await chat_repo.get_by_id(chat.id)
    if not refreshed:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_chat_response(refreshed)


@router.get("/{strategyId:uuid}", response_model=StrategyResponse)
async def get_strategy(
    strategyId: UUID,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Get a strategy (chat) by ID."""
    chat = await get_owned_chat_or_404(chat_repo, strategyId, user_id)

    # Lazy detail fetch: if this is a WDK-linked chat with no plan data,
    # fetch the full detail from WDK now (summary-only chats are created
    # during sync-wdk to avoid the N+1 problem).
    chat = await lazy_fetch_wdk_detail(chat=chat, chat_repo=chat_repo)

    # Interactive plan artifacts now stream through the chat pipeline as
    # ``data-plan-artifact`` parts and are held in ``usePlanStore`` on the
    # client, so there is no server-side plan restoration path.
    return build_chat_response(chat)


@router.patch("/{strategyId:uuid}", response_model=StrategyResponse)
async def update_strategy(
    strategyId: UUID,
    request: UpdateStrategyRequest,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Update strategy metadata (name, plan, wdk link, saved flag)."""
    await get_owned_chat_or_404(chat_repo, strategyId, user_id)

    payload: StrategyPlanPayload | None = None
    record_type: str | None = None
    if request.plan:
        plan_in = request.plan.model_dump(exclude_none=True)
        payload = validate_plan_or_raise(plan_in)
        record_type = payload.record_type

    fields_set: set[str] = getattr(request, "model_fields_set", set())
    wdk_strategy_id_set = "wdk_strategy_id" in fields_set
    is_saved_set = "is_saved" in fields_set

    await chat_repo.update_chat(
        strategyId,
        ChatUpdate(
            name=request.name,
            plan=payload,
            record_type=record_type,
            wdk_strategy_id=request.wdk_strategy_id,
            wdk_strategy_id_set=wdk_strategy_id_set,
            is_saved=request.is_saved,
            is_saved_set=is_saved_set,
            step_count=len(walk_step_tree(payload.root)) if payload else None,
        ),
    )

    updated = await chat_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    if is_saved_set and updated.wdk_strategy_id:
        await sync_is_saved_to_wdk(chat=updated)

    return build_chat_response(updated)


@router.post("/{strategyId:uuid}/push", response_model=StrategyResponse)
async def push_strategy(
    strategyId: UUID,
    request: PushStrategyRequest,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Push a strategy to WDK: normalize plan, persist locally, sync to WDK."""
    chat = await get_owned_chat_or_404(chat_repo, strategyId, user_id)

    plan_in = request.plan.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan_in)

    payload = await canonicalize_plan_parameters(
        plan=payload, site_id=request.site_id,
    )

    # Preserve WDK sync state from existing chat — old values fill
    # in where the new payload has None; new values always take precedence.
    sync_fields = {"wdk_step_ids", "step_counts", "step_validations"}
    if chat.plan:
        old = StrategyPlanPayload.model_validate(chat.plan)
        preserved = old.model_dump(include=sync_fields, exclude_none=True)
        current = payload.model_dump(include=sync_fields, exclude_none=True)
        merged = {**preserved, **current}
        if merged:
            payload = payload.model_copy(update=merged)

    await chat_repo.update_chat(
        strategyId,
        ChatUpdate(
            name=request.name,
            plan=payload,
            record_type=payload.record_type,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )

    wdk_strategy_id: int | None = chat.wdk_strategy_id
    strategy_graph_persisted = PersistedStrategyGraph(
        id=str(strategyId),
        name=request.name,
        plan=payload,
        wdk_strategy_id=wdk_strategy_id,
    )
    session = build_strategy_session(
        site_id=request.site_id, strategy_graph=strategy_graph_persisted
    )
    graph = session.get_graph(None)
    if graph is not None:
        sync_state = ensure_sync_state(session)
        failed_steps = await push_all_steps_to_wdk(
            graph, sync_state, request.site_id, update_existing=True,
        )
        if failed_steps:
            logger.warning(
                "Some steps failed to push to WDK",
                strategy_id=str(strategyId),
                failed_steps=failed_steps,
            )

        sync_result = await sync_strategy_for_site(
            graph=graph,
            sync_state=sync_state,
            site_id=request.site_id,
            strategy_name=request.name,
        )
        wdk_strategy_id = sync_result.wdk_strategy_id

        await chat_repo.update_chat(
            strategyId,
            ChatUpdate(
                wdk_strategy_id=wdk_strategy_id,
                wdk_strategy_id_set=True,
            ),
        )

    updated = await chat_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_chat_response(updated)


@router.delete("/{strategyId:uuid}", status_code=204, response_class=Response)
async def delete_strategy(
    strategyId: UUID,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
    *,
    delete_from_wdk: Annotated[bool, Query(alias="deleteFromWdk")] = False,
) -> Response:
    """Delete a strategy.

    For WDK-linked strategies with ``deleteFromWdk=false`` (default), the
    chat is soft-deleted (dismissed) to prevent WDK sync from re-importing it.
    Pass ``deleteFromWdk=true`` to hard-delete from both PathFinder and WDK.
    Non-WDK strategies are always hard-deleted.
    """
    chat = await get_owned_chat_or_404(chat_repo, strategyId, user_id)

    is_wdk_linked = chat.wdk_strategy_id is not None

    if is_wdk_linked and not delete_from_wdk:
        await chat_repo.dismiss(strategyId)
    else:
        if delete_from_wdk and chat.wdk_strategy_id and chat.site_id:
            try:
                api = get_strategy_api(chat.site_id)
                await api.delete_strategy(chat.wdk_strategy_id)
            except (AppError, OSError, RuntimeError) as e:
                logger.warning(
                    "WDK strategy delete failed",
                    wdk_strategy_id=chat.wdk_strategy_id,
                    error=str(e),
                )
        await chat_repo.delete(strategyId)

    return Response(status_code=204)


@router.get("/{strategyId:uuid}/ast")
async def get_strategy_ast(
    strategyId: UUID,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> JSONObject:
    """Return the raw plan AST from a strategy chat."""
    chat = await get_owned_chat_or_404(chat_repo, strategyId, user_id)
    if not chat.plan:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy has no plan AST",
        )
    return chat.plan


@router.post("/{strategyId:uuid}/restore", response_model=StrategyResponse)
async def restore_strategy(
    strategyId: UUID,
    chat_repo: ChatRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Restore a dismissed (soft-deleted) strategy.

    Clears dismissed_at and resets plan to empty (triggers lazy WDK re-fetch).
    """
    chat = await get_owned_chat_or_404(chat_repo, strategyId, user_id)
    if chat.dismissed_at is None:
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
    await chat_repo.restore(strategyId)

    updated = await chat_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_chat_summary(updated)
