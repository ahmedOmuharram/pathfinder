"""Sidebar-specific conversation endpoints: dismiss, duplicate, messages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status

from pathfinder.ai.conversation.event_stream import latest_event_with_timestamp
from pathfinder.persistence.repositories import (
    ConversationRepository,
    MessagesRepository,
)
from pathfinder.transport.http.deps import CurrentUser, DBSession
from pathfinder.transport.http.schemas import ConversationDuplicateResponse

# A turn whose latest event is older than this is presumed dead (worker
# crashed, network died mid-stream). The in-flight assistant message stays
# visible after this window so users don't lose access to a stranded row.
STUCK_TURN_TTL = timedelta(seconds=60)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


def _message_to_ui_message(
    *,
    id_: UUID,
    role: str,
    parts: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": str(id_),
        "role": role,
        "parts": parts,
        "metadata": metadata,
    }


@router.post(
    "/{conversation_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a conversation (hide from sidebar).",
)
async def dismiss_conversation(
    conversation_id: UUID, session: DBSession, user_id: CurrentUser,
) -> None:
    repo = ConversationRepository(session)
    existing = await repo.get_by_id(conversation_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    await repo.dismiss(conversation_id)
    await session.commit()


@router.post(
    "/{conversation_id}/duplicate",
    response_model=ConversationDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a conversation (new row + copied messages).",
)
async def duplicate_conversation(
    conversation_id: UUID, session: DBSession, user_id: CurrentUser,
) -> ConversationDuplicateResponse:
    conv_repo = ConversationRepository(session)
    source = await conv_repo.get_by_id(conversation_id)
    if source is None or source.user_id != user_id:
        raise HTTPException(status_code=404, detail="conversation not found")

    msg_repo = MessagesRepository(session)
    new_conv = await conv_repo.create(
        user_id=user_id,
        site_id=source.site_id,
        name=source.name or "Conversation",
    )

    for row in await msg_repo.list_messages_for_conversation(conversation_id):
        await msg_repo.insert_message(
            message_id=uuid4(),
            conversation_id=new_conv.id,
            role=row.role,
            parts=row.parts,
            metadata=row.metadata_,
        )

    await session.commit()
    return ConversationDuplicateResponse(id=new_conv.id, name=new_conv.name)


@router.get(
    "/{conversation_id}/messages",
    response_model=list[dict[str, Any]],
    summary="Ordered UIMessage[] history (oldest first).",
)
async def list_conversation_messages(
    conversation_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> list[dict[str, Any]]:
    del user_id
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id must be a UUID",
        ) from exc
    repo = MessagesRepository(session)
    rows = await repo.list_messages_for_conversation(conv_uuid)
    tip = await latest_event_with_timestamp(conv_uuid)
    if (
        tip is not None
        and tip[1].get("type") != "done"
        and datetime.now(tz=UTC) - tip[2] < STUCK_TURN_TTL
        and rows
        and rows[-1].role == "assistant"
    ):
        rows = rows[:-1]
    return [
        _message_to_ui_message(
            id_=row.id, role=row.role, parts=row.parts, metadata=row.metadata_,
        )
        for row in rows
    ]
