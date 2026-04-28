"""Specialist mode enter/exit endpoints.

Per design spec ``2026-04-26-specialist-commands-design.md``. Setting
``specialist_mode`` on the conversation row swaps the LangGraph entry node
on the next turn (see ``apps/api/src/pathfinder/ai/graph/builder.py``).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents._model_resolution import resolve_specialist_model_id
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.models.catalog import get_model_entry
from pathfinder.ai.specialists.concurrency import (
    ActiveSessionConflictError,
    assert_no_active_session,
    assert_no_inflight_durable_task,
)
from pathfinder.ai.specialists.context import (
    build_research_context,
    build_validate_context,
    now_utc,
)
from pathfinder.ai.specialists.types import (
    ResearchContext,
    SpecialistContext,
    SpecialistKind,
    SpecialistMode,
    ValidateContext,
)
from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.repositories.conversation import ConversationUpdate
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.user_preferences import set_specialist_default
from pathfinder.transport.http.deps import (
    ConversationRepo,
    CurrentUser,
)
from pathfinder.transport.http.routers._authz import (
    get_owned_conversation_or_404,
)
from pathfinder.transport.http.schemas.specialists import (
    SpecialistEnterRequest,
    SpecialistEnterResponse,
    SpecialistExitResponse,
    SpecialistStateResponse,
    SpecialistStateUpdate,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["specialists"])
logger = get_logger(__name__)


def _parse_focused_step_id(arg: str) -> int | None:
    arg = arg.strip()
    if not arg:
        return None
    try:
        return int(arg)
    except ValueError:
        return None


def _conflict_to_error(conflict: ActiveSessionConflictError) -> AppError:
    return AppError(
        code=ErrorCode.SESSION_CONFLICT,
        title="Active session conflict",
        status=409,
        detail=conflict.detail,
        errors=[{"reason": conflict.reason.value}],
    )


def _validate_preconditions(
    *, kind: SpecialistKind, conversation: Conversation,
) -> None:
    if kind != "validate":
        return
    if conversation.step_count < 1:
        raise AppError(
            code=ErrorCode.SPECIALIST_PRECONDITION_FAILED,
            title="Validate requires a strategy",
            status=409,
            detail=(
                "Validate mode needs at least one step. Build the strategy "
                "first, then try /validate again."
            ),
        )
    if not conversation.site_id:
        raise AppError(
            code=ErrorCode.SPECIALIST_PRECONDITION_FAILED,
            title="Validate requires a site",
            status=409,
            detail="Validate needs a selected site (PlasmoDB, ToxoDB, ...).",
        )


async def _build_context_for_kind(
    *,
    kind: SpecialistKind,
    request: Request,
    session: AsyncSession,
    conversation: Conversation,
    arg: str,
    extraction_model_id: str | None,
) -> SpecialistContext:
    raw_store = getattr(request.app.state, "memory_store", None)
    memory_store = MemoryStore(store=raw_store) if raw_store is not None else None
    if kind == "validate":
        return await build_validate_context(
            session=session,
            conversation=conversation,
            focused_step_id=_parse_focused_step_id(arg),
            memory_store=memory_store,
            extraction_model_id=extraction_model_id,
        )
    return await build_research_context(
        session=session,
        conversation=conversation,
        research_question=arg,
        memory_store=memory_store,
        extraction_model_id=extraction_model_id,
    )


def _entered_part_payload(
    *,
    kind: SpecialistKind,
    model_id: str,
    context: SpecialistContext,
) -> dict[str, object]:
    summary = (
        context.research_question if isinstance(context, ResearchContext)
        else context.user_success_criteria
        if isinstance(context, ValidateContext)
        else ""
    )
    return {
        "type": "data-specialist-entered",
        "data": {
            "kind": kind,
            "modelId": model_id,
            "contextSummary": summary[:280],
        },
    }


def _exited_part_payload() -> dict[str, object]:
    return {
        "type": "data-specialist-exited",
        "data": {},
    }


@router.post(
    "/{conversation_id}/specialists/{kind}/enter",
    response_model=SpecialistEnterResponse,
)
async def enter_specialist(
    conversation_id: Annotated[UUID, Path()],
    kind: Annotated[SpecialistKind, Path()],
    body: SpecialistEnterRequest,
    request: Request,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> SpecialistEnterResponse:
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    try:
        await assert_no_active_session(conversation=conversation)
    except ActiveSessionConflictError as conflict:
        raise _conflict_to_error(conflict) from conflict

    _validate_preconditions(kind=kind, conversation=conversation)

    user = await conv_repo.session.get(User, user_id)
    if user is None:
        raise NotFoundError(title="User not found")
    model_id = await resolve_specialist_model_id(
        command=kind, user=user, explicit=body.model_id,
    )

    context = await _build_context_for_kind(
        kind=kind,
        request=request,
        session=conv_repo.session,
        conversation=conversation,
        arg=body.arg,
        extraction_model_id=model_id,
    )

    mode = SpecialistMode(
        kind=kind,
        entered_at=now_utc(),
        model_id=model_id,
        context=context,
    )
    await conv_repo.update_conversation(
        conversation_id,
        ConversationUpdate(
            specialist_mode=mode.model_dump(by_alias=True, mode="json"),
            specialist_mode_set=True,
        ),
    )
    await set_specialist_default(
        conv_repo.session,
        user_id=user_id,
        command=kind,
        model_id=model_id,
    )

    message_id = uuid4()
    await MessagesRepository(conv_repo.session).insert_message(
        message_id=message_id,
        conversation_id=conversation_id,
        role="assistant",
        parts=[
            _entered_part_payload(
                kind=kind, model_id=model_id, context=context,
            ),
        ],
        metadata={},
    )
    await conv_repo.session.commit()

    logger.info(
        "specialist entered",
        conversation_id=str(conversation_id),
        kind=kind,
        model_id=model_id,
    )

    return SpecialistEnterResponse(
        message_id=message_id,
        kind=kind,
        model_id=model_id,
        context=context,
    )


@router.post(
    "/{conversation_id}/specialists/exit",
    response_model=SpecialistExitResponse,
)
async def exit_specialist(
    conversation_id: Annotated[UUID, Path()],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> SpecialistExitResponse:
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    if conversation.specialist_mode is None:
        return SpecialistExitResponse(cleared=False, message_id=None)

    try:
        await assert_no_inflight_durable_task(
            conversation_id=conversation_id,
        )
    except ActiveSessionConflictError as conflict:
        raise _conflict_to_error(conflict) from conflict

    message_id = uuid4()
    await MessagesRepository(conv_repo.session).insert_message(
        message_id=message_id,
        conversation_id=conversation_id,
        role="assistant",
        parts=[_exited_part_payload()],
        metadata={},
    )
    await conv_repo.update_conversation(
        conversation_id,
        ConversationUpdate(
            specialist_mode=None,
            specialist_mode_set=True,
        ),
    )
    await conv_repo.session.commit()

    logger.info(
        "specialist exited",
        conversation_id=str(conversation_id),
    )

    return SpecialistExitResponse(cleared=True, message_id=message_id)




@router.patch(
    "/{conversation_id}/specialists/state",
    response_model=SpecialistStateResponse,
)
async def update_specialist_state(
    conversation_id: Annotated[UUID, Path()],
    body: SpecialistStateUpdate,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> SpecialistStateResponse:
    """Swap fields on the active specialist mode mid-session.

    Currently only ``model_id`` is mutable. Validated against the catalog;
    persisted both onto ``Conversation.specialist_mode.model_id`` and the
    user's sticky default for that command.
    """
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    if conversation.specialist_mode is None:
        raise AppError(
            code=ErrorCode.SPECIALIST_PRECONDITION_FAILED,
            title="No active specialist mode",
            status=409,
            detail=(
                "There is no active specialist mode on this conversation. "
                "Enter /validate or /research first."
            ),
        )
    if get_model_entry(body.model_id) is None:
        raise ValidationError(
            detail=f"Unknown model id: {body.model_id}",
        )

    try:
        mode = SpecialistMode.model_validate(conversation.specialist_mode)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=ErrorCode.SPECIALIST_PRECONDITION_FAILED,
            title="Specialist state corrupted",
            status=409,
            detail="Could not parse current specialist mode.",
        ) from exc

    new_mode = mode.model_copy(update={"model_id": body.model_id})
    await conv_repo.update_conversation(
        conversation_id,
        ConversationUpdate(
            specialist_mode=new_mode.model_dump(by_alias=True, mode="json"),
            specialist_mode_set=True,
        ),
    )
    await set_specialist_default(
        conv_repo.session,
        user_id=user_id,
        command=mode.kind,
        model_id=body.model_id,
    )
    await conv_repo.session.commit()

    logger.info(
        "specialist model swapped",
        conversation_id=str(conversation_id),
        kind=mode.kind,
        model_id=body.model_id,
    )

    return SpecialistStateResponse(kind=mode.kind, model_id=body.model_id)
