"""Chat (conversation) HTTP surface.

Drives the sidebar — listing active + dismissed conversations, renaming,
dismissing/restoring/deleting, duplicating — plus the per-chat messages
history endpoint consumed on initial load.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status

from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import ChatRepository, MessagesRepository
from pathfinder.persistence.repositories.chat import ChatUpdate
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/chats", tags=["chat"])


class ChatListItem(CamelModel):
    """Minimal sidebar projection of a :class:`Chat` row."""

    id: UUID
    name: str
    site_id: str
    experiment_id: str | None
    wdk_strategy_id: int | None
    is_saved: bool
    step_count: int
    estimated_size: int | None
    dismissed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChatPatchBody(CamelModel):
    """Partial update body for a chat.

    Fields absent from the body are left unchanged; ``None`` is reserved
    for future "unset" semantics and currently rejected for ``name``.
    """

    name: str | None = None
    is_saved: bool | None = None


class ChatDuplicateResponse(CamelModel):
    id: UUID
    name: str


def _to_list_item(chat: Chat) -> ChatListItem:
    return ChatListItem(
        id=chat.id,
        name=chat.name,
        site_id=chat.site_id,
        experiment_id=chat.experiment_id,
        wdk_strategy_id=chat.wdk_strategy_id,
        is_saved=chat.is_saved,
        step_count=chat.step_count,
        estimated_size=chat.estimated_size,
        dismissed_at=chat.dismissed_at,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


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


async def _require_owned_chat(
    session: DBSession, chat_id: UUID, user_id: UUID,
) -> Chat:
    chat = await ChatRepository(session).get_by_id(chat_id)
    if chat is None or chat.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="chat not found",
        )
    return chat


@router.get(
    "",
    response_model=list[ChatListItem],
    summary="List active conversations for the authenticated user.",
)
async def list_chats(
    session: DBSession,
    user_id: CurrentUser,
    site_id: str | None = None,
    limit: int = 50,
) -> list[ChatListItem]:
    chats = await ChatRepository(session).list_chats(
        user_id=user_id, site_id=site_id, limit=limit,
    )
    return [_to_list_item(c) for c in chats]


@router.get(
    "/dismissed",
    response_model=list[ChatListItem],
    summary="List dismissed (soft-deleted) conversations.",
)
async def list_dismissed_chats(
    session: DBSession,
    user_id: CurrentUser,
    site_id: str | None = None,
    limit: int = 50,
) -> list[ChatListItem]:
    chats = await ChatRepository(session).list_dismissed_chats(
        user_id=user_id, site_id=site_id, limit=limit,
    )
    return [_to_list_item(c) for c in chats]


@router.patch(
    "/{chat_id}",
    response_model=ChatListItem,
    summary="Patch a conversation (rename, toggle saved).",
)
async def patch_chat(
    chat_id: UUID,
    body: ChatPatchBody,
    session: DBSession,
    user_id: CurrentUser,
) -> ChatListItem:
    await _require_owned_chat(session, chat_id, user_id)
    repo = ChatRepository(session)
    upd = ChatUpdate()
    if body.name is not None:
        upd.name = body.name
    if body.is_saved is not None:
        upd.is_saved = body.is_saved
        upd.is_saved_set = True
    await repo.update_chat(chat_id, upd)
    await session.commit()
    refreshed = await repo.get_by_id(chat_id)
    assert refreshed is not None  # noqa: S101 — just updated
    return _to_list_item(refreshed)


@router.post(
    "/{chat_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a conversation (hide from main sidebar list).",
)
async def dismiss_chat(
    chat_id: UUID, session: DBSession, user_id: CurrentUser,
) -> None:
    await _require_owned_chat(session, chat_id, user_id)
    await ChatRepository(session).dismiss(chat_id)
    await session.commit()


@router.post(
    "/{chat_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Un-dismiss a conversation.",
)
async def restore_chat(
    chat_id: UUID, session: DBSession, user_id: CurrentUser,
) -> None:
    await _require_owned_chat(session, chat_id, user_id)
    await ChatRepository(session).restore(chat_id)
    await session.commit()


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete a conversation and its messages.",
)
async def delete_chat(
    chat_id: UUID, session: DBSession, user_id: CurrentUser,
) -> None:
    await _require_owned_chat(session, chat_id, user_id)
    await ChatRepository(session).delete(chat_id)
    await session.commit()


@router.post(
    "/{chat_id}/duplicate",
    response_model=ChatDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a conversation (new row + copied messages).",
)
async def duplicate_chat(
    chat_id: UUID, session: DBSession, user_id: CurrentUser,
) -> ChatDuplicateResponse:
    """Create a new chat rooted from this one.

    Copies the row (name deduplicated) and all persisted message rows.
    Graph checkpoints are **not** cloned — the new thread starts fresh
    and the graph will re-ingest the copied messages on the first turn.
    """
    source = await _require_owned_chat(session, chat_id, user_id)
    chat_repo = ChatRepository(session)
    msg_repo = MessagesRepository(session)

    new_chat = await chat_repo.create(
        user_id=user_id,
        site_id=source.site_id,
        name=source.name or "Conversation",
    )

    for row in await msg_repo.list_messages_for_chat(chat_id):
        await msg_repo.insert_message(
            message_id=uuid4(),
            chat_id=new_chat.id,
            role=row.role,
            parts=row.parts,
            metadata=row.metadata_,
        )

    await session.commit()
    return ChatDuplicateResponse(id=new_chat.id, name=new_chat.name)


@router.get(
    "/{chat_id}/messages",
    response_model=list[dict[str, Any]],
    summary="Ordered UIMessage[] history for a chat (oldest first).",
)
async def list_chat_messages(
    chat_id: str,
    session: DBSession,
    user_id: CurrentUser,
) -> list[dict[str, Any]]:
    del user_id  # route is per-user via session; no per-row ownership yet
    try:
        chat_uuid = UUID(chat_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chat_id must be a UUID",
        ) from exc
    repo = MessagesRepository(session)
    rows = await repo.list_messages_for_chat(chat_uuid)
    return [
        _message_to_ui_message(
            id_=row.id, role=row.role, parts=row.parts, metadata=row.metadata_,
        )
        for row in rows
    ]
