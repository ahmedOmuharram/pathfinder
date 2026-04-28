"""Strategy CRUD endpoints.

Backed by the ``chats`` table (one row per conversation with strategy
metadata: name, wdk_strategy_id, plan, step_count, etc.). See
``persistence/models.py`` and ``persistence/repositories/chat.py``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from pathfinder.ai.models.catalog import get_model_entry
from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.repositories import ConversationUpdate
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.conversations.begin import begin_conversation
from pathfinder.services.conversations.fork import (
    ForkError,
    fork_conversation,
)
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_strategy_ast_parameters,
)
from pathfinder.services.strategies.plan_validation import validate_plan_or_raise
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.step_push_planner import (
    CreateAction,
    RecreateAction,
    plan_step_pushes,
    topology_changed,
)
from pathfinder.services.strategies.step_wdk_push import push_steps_with_plan
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state
from pathfinder.services.strategies.wdk_sync import (
    lazy_fetch_wdk_detail,
    sync_is_saved_to_wdk,
)
from pathfinder.services.wdk import get_strategy_api
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser, DBSession
from pathfinder.transport.http.routers._authz import get_owned_conversation_or_404
from pathfinder.transport.http.schemas import (
    BeginConversationRequest,
    BeginConversationResponse,
    ConversationResponse,
    CreateConversationRequest,
    PushConversationRequest,
    UpdateConversationRequest,
)
from pathfinder.transport.http.schemas.conversations import (
    ForkConversationRequest,
)

from ._shared import (
    build_conversation_response,
    build_conversation_summary,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])
logger = get_logger(__name__)


@router.get("", response_model=list[ConversationResponse])
async def list_strategies(
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[ConversationResponse]:
    """List the user's chats (active, non-dismissed)."""
    conversations = await conv_repo.list_conversations(user_id, site_id)
    return [build_conversation_summary(c, site_id=site_id or "") for c in conversations]


@router.get("/dismissed", response_model=list[ConversationResponse])
async def list_dismissed_strategies(
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[ConversationResponse]:
    """List the user's dismissed (soft-deleted) chats."""
    conversations = await conv_repo.list_dismissed_conversations(user_id, site_id)
    return [build_conversation_summary(c, site_id=site_id or "") for c in conversations]


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_strategy(
    request: CreateConversationRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Create a new strategy (chat with plan metadata)."""
    plan_in = request.strategy_ast.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan_in)

    conversation = await conv_repo.create(
        user_id=user_id,
        site_id=request.site_id,
        name=request.name,
    )
    await conv_repo.update_conversation(
        conversation.id,
        ConversationUpdate(
            strategy_ast=payload,
            record_type=payload.record_type,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )

    refreshed = await conv_repo.get_by_id(conversation.id)
    if not refreshed:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_conversation_response(refreshed)


@router.get("/{strategyId:uuid}", response_model=ConversationResponse)
async def get_strategy(
    strategyId: UUID,
    conv_repo: ConversationRepo,
    session: DBSession,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Get a strategy (chat) by ID."""
    conversation = await get_owned_conversation_or_404(conv_repo, strategyId, user_id)

    # Lazy detail fetch: if this is a WDK-linked chat with no plan data,
    # fetch the full detail from WDK now (summary-only chats are created
    # during sync-wdk to avoid the N+1 problem).
    conversation = await lazy_fetch_wdk_detail(conversation=conversation, conv_repo=conv_repo)

    messages_repo = MessagesRepository(session)
    total_tokens, total_cost = await messages_repo.sum_usage_for_conversation(
        conversation.id,
    )

    return build_conversation_response(
        conversation,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
    )


@router.patch("/{strategyId:uuid}", response_model=ConversationResponse)
async def update_strategy(
    strategyId: UUID,
    request: UpdateConversationRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Update strategy metadata (name, plan, wdk link, saved flag)."""
    await get_owned_conversation_or_404(conv_repo, strategyId, user_id)

    payload: StrategyAst | None = None
    record_type: str | None = None
    if request.strategy_ast:
        plan_in = request.strategy_ast.model_dump(exclude_none=True)
        payload = validate_plan_or_raise(plan_in)
        record_type = payload.record_type

    fields_set: set[str] = getattr(request, "model_fields_set", set())
    wdk_strategy_id_set = "wdk_strategy_id" in fields_set
    is_saved_set = "is_saved" in fields_set
    supervisor_model_id_set = "supervisor_model_id" in fields_set
    if (
        supervisor_model_id_set
        and request.supervisor_model_id is not None
        and get_model_entry(request.supervisor_model_id) is None
    ):
        raise ValidationError(
            title="Unknown supervisor model",
            detail=f"Unknown supervisor_model_id: {request.supervisor_model_id}",
        )

    await conv_repo.update_conversation(
        strategyId,
        ConversationUpdate(
            name=request.name,
            strategy_ast=payload,
            record_type=record_type,
            wdk_strategy_id=request.wdk_strategy_id,
            wdk_strategy_id_set=wdk_strategy_id_set,
            is_saved=request.is_saved,
            is_saved_set=is_saved_set,
            step_count=len(walk_step_tree(payload.root)) if payload else None,
            supervisor_model_id=request.supervisor_model_id,
            supervisor_model_id_set=supervisor_model_id_set,
        ),
    )

    updated = await conv_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    if is_saved_set and updated.wdk_strategy_id:
        await sync_is_saved_to_wdk(conversation=updated)

    return build_conversation_response(updated)


@router.post("/{strategyId:uuid}/fork", response_model=ConversationResponse)
async def fork_strategy(
    strategyId: UUID,
    request: ForkConversationRequest,
    conv_repo: ConversationRepo,
    session: DBSession,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Branch a conversation at a chosen assistant message into a new chat."""
    await get_owned_conversation_or_404(conv_repo, strategyId, user_id)
    try:
        fork = await fork_conversation(
            session,
            source_conversation_id=strategyId,
            from_message_id=request.from_message_id,
            user_id=user_id,
        )
    except ForkError as exc:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title=str(exc),
        ) from exc
    await session.commit()
    return build_conversation_summary(fork, site_id=fork.site_id)


def _combine_op_snapshot(node: object) -> list[dict[str, object]]:
    """Walk an AST tree and return ``[{id, operator}]`` for every combine.
    Used by ``push_strategy`` debug logs to trace operator preservation
    through the validate → canonicalize → persist → derive round-trip."""
    out: list[dict[str, object]] = []
    stack: list[object] = [node]
    while stack:
        cur = stack.pop()
        secondary = getattr(cur, "secondary_input", None)
        operator = getattr(cur, "operator", None)
        if secondary is not None:
            out.append(
                {
                    "id": getattr(cur, "id", None),
                    "operator": operator.value if operator is not None else None,
                    "search_name": getattr(cur, "search_name", None),
                },
            )
        primary = getattr(cur, "primary_input", None)
        if primary is not None:
            stack.append(primary)
        if secondary is not None:
            stack.append(secondary)
    return out


@router.post("/{strategyId:uuid}/push", response_model=ConversationResponse)
async def push_strategy(
    strategyId: UUID,
    request: PushConversationRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Push a strategy to WDK: normalize plan, persist locally, sync to WDK."""
    conversation = await get_owned_conversation_or_404(conv_repo, strategyId, user_id)

    plan_in = request.strategy_ast.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan_in)
    logger.info(
        "DEBUG push.combine_ops.received",
        strategy_id=str(strategyId),
        ops=_combine_op_snapshot(payload.root),
    )

    payload = await canonicalize_strategy_ast_parameters(
        strategy_ast=payload, site_id=request.site_id,
    )
    logger.info(
        "DEBUG push.combine_ops.after_canonicalize",
        strategy_id=str(strategyId),
        ops=_combine_op_snapshot(payload.root),
    )

    # Preserve WDK sync state from existing chat — old values fill
    # in where the new payload has None; new values always take precedence.
    sync_fields = {"wdk_step_ids", "step_counts", "step_validations"}
    old_ast: StrategyAst | None = None
    if conversation.strategy_ast:
        old_ast = StrategyAst.model_validate(conversation.strategy_ast)
        preserved = old_ast.model_dump(include=sync_fields, exclude_none=True)
        current = payload.model_dump(include=sync_fields, exclude_none=True)
        merged = {**preserved, **current}
        if merged:
            payload = payload.model_copy(update=merged)

    await conv_repo.update_conversation(
        strategyId,
        ConversationUpdate(
            name=request.name,
            strategy_ast=payload,
            record_type=payload.record_type,
            step_count=len(walk_step_tree(payload.root)),
        ),
    )

    wdk_strategy_id: int | None = conversation.wdk_strategy_id
    strategy_graph_persisted = PersistedStrategyGraph(
        id=str(strategyId),
        name=request.name,
        strategy_ast=payload,
        wdk_strategy_id=wdk_strategy_id,
    )
    session = build_strategy_session(
        site_id=request.site_id, strategy_graph=strategy_graph_persisted
    )
    graph = session.get_graph(None)
    if graph is not None:
        sync_state = ensure_sync_state(session)
        plan = plan_step_pushes(
            old_ast=old_ast,
            new_ast=payload,
            existing_wdk_ids=sync_state.wdk_step_ids,
        )
        has_recreate = any(isinstance(p.action, RecreateAction) for p in plan)
        has_create = any(isinstance(p.action, CreateAction) for p in plan)
        topology_changed_flag = topology_changed(old_ast, payload)
        sync_strategy_skipped = not (
            topology_changed_flag or has_recreate or has_create
        )
        logger.info(
            "DEBUG push.plan",
            strategy_id=str(strategyId),
            actions=[(p.step_id, p.action.kind) for p in plan],
            topology_changed=topology_changed_flag,
            sync_strategy_skipped=sync_strategy_skipped,
        )

        failed_steps = await push_steps_with_plan(
            graph, sync_state, request.site_id, plan,
        )
        if failed_steps:
            logger.warning(
                "Some steps failed to push to WDK",
                strategy_id=str(strategyId),
                failed_steps=failed_steps,
            )

        if not sync_strategy_skipped:
            sync_result = await sync_strategy_for_site(
                graph=graph,
                sync_state=sync_state,
                site_id=request.site_id,
                strategy_name=request.name,
            )
            wdk_strategy_id = sync_result.wdk_strategy_id

            await conv_repo.update_conversation(
                strategyId,
                ConversationUpdate(
                    wdk_strategy_id=wdk_strategy_id,
                    wdk_strategy_id_set=True,
                ),
            )

    updated = await conv_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    response = build_conversation_response(updated)
    logger.info(
        "DEBUG push.combine_ops.response",
        strategy_id=str(strategyId),
        ops=[
            {"id": s.id, "operator": s.operator, "search_name": s.search_name}
            for s in response.steps
            if s.kind == "combine"
        ],
    )
    return response


@router.delete("/{strategyId:uuid}", status_code=204, response_class=Response)
async def delete_strategy(
    strategyId: UUID,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
    *,
    delete_from_wdk: Annotated[bool, Query(alias="deleteFromWdk")] = False,
    cascade: Annotated[bool, Query()] = False,
) -> Response:
    """Delete a strategy.

    For WDK-linked strategies with ``deleteFromWdk=false`` (default), the
    chat is soft-deleted (dismissed) to prevent WDK sync from re-importing it.
    Pass ``deleteFromWdk=true`` to hard-delete from both PathFinder and WDK.
    Non-WDK strategies are always hard-deleted.

    With ``cascade=true`` on hard-delete, the whole fork subtree goes; with
    ``cascade=false`` (default), direct children climb up to this node's
    parent so the tree stays connected.
    """
    conversation = await get_owned_conversation_or_404(conv_repo, strategyId, user_id)

    is_wdk_linked = conversation.wdk_strategy_id is not None

    if is_wdk_linked and delete_from_wdk and conversation.wdk_strategy_id is not None:
        consumers = await conv_repo.list_consumers_of_saved_strategy(
            user_id,
            conversation.wdk_strategy_id,
            exclude_conversation_id=strategyId,
        )
        if consumers:
            consumer_names = ", ".join(c.name for c in consumers[:5])
            raise ValidationError(
                title="saved strategy still in use",
                detail=(
                    f"{len(consumers)} other conversation(s) import this saved "
                    f"strategy: {consumer_names}"
                ),
            )

    if is_wdk_linked and not delete_from_wdk:
        await conv_repo.dismiss(strategyId)
    else:
        if delete_from_wdk and conversation.wdk_strategy_id and conversation.site_id:
            try:
                api = get_strategy_api(conversation.site_id)
                await api.delete_strategy(conversation.wdk_strategy_id)
            except (AppError, OSError, RuntimeError) as e:
                logger.warning(
                    "WDK strategy delete failed",
                    wdk_strategy_id=conversation.wdk_strategy_id,
                    error=str(e),
                )
        await conv_repo.delete(strategyId, cascade=cascade)

    return Response(status_code=204)


@router.get("/{strategyId:uuid}/ast")
async def get_strategy_ast(
    strategyId: UUID,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> JSONObject:
    """Return the raw plan AST from a strategy chat."""
    conversation = await get_owned_conversation_or_404(conv_repo, strategyId, user_id)
    if not conversation.strategy_ast:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy has no plan AST",
        )
    return conversation.strategy_ast


@router.post("/{strategyId:uuid}/restore", response_model=ConversationResponse)
async def restore_strategy(
    strategyId: UUID,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Restore a dismissed (soft-deleted) strategy.

    Clears dismissed_at and resets plan to empty (triggers lazy WDK re-fetch).
    """
    conversation = await get_owned_conversation_or_404(conv_repo, strategyId, user_id)
    if conversation.dismissed_at is None:
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
    await conv_repo.restore(strategyId)

    updated = await conv_repo.get_by_id(strategyId)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    return build_conversation_summary(updated)


@router.post(
    "/{conversation_id}/begin",
    response_model=BeginConversationResponse,
)
async def begin_strategy(
    conversation_id: Annotated[UUID, "Conversation id (client-generated UUID)."],
    body: BeginConversationRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> BeginConversationResponse:
    """Idempotent first-action setup for a conversation.

    Inserts the row if missing (``ON CONFLICT (id) DO NOTHING``), schedules
    title generation when ``seedText`` is provided on a fresh row, and
    returns the conversation. Every first-action client (chat send, slash
    command, launcher) calls this before its own request so downstream
    endpoints can assume the row exists.
    """
    existing = await conv_repo.get_by_id(conversation_id)
    if existing is not None and existing.user_id != user_id:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found",
        )

    result = await begin_conversation(
        session=conv_repo.session,
        conversation_id=conversation_id,
        user_id=user_id,
        site_id=body.site_id,
        experiment_id=body.experiment_id,
        seed_text=body.seed_text,
    )
    await conv_repo.session.commit()
    return BeginConversationResponse(
        conversation_id=result.conversation.id,
        is_new=result.is_new,
        name=result.conversation.name,
    )
