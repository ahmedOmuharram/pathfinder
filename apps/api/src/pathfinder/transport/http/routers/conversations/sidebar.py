from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from pathfinder.persistence.repositories import (
    ConversationRepository,
    MessagesRepository,
)
from pathfinder.transport.http.deps import CurrentUser, DBSession
from pathfinder.transport.http.schemas import ConversationDuplicateResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


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
            metadata=row.metadata_,
        )

    await session.execute(
        text(
            """
            INSERT INTO conversation_events (
                conversation_id, turn_id, task_id, chunk
            )
            SELECT :dst, turn_id, task_id, chunk
            FROM conversation_events
            WHERE conversation_id = :src
            ORDER BY id ASC
            """,
        ),
        {"src": str(conversation_id), "dst": str(new_conv.id)},
    )

    await session.commit()
    return ConversationDuplicateResponse(id=new_conv.id, name=new_conv.name)
