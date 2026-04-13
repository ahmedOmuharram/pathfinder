"""Chat history endpoint.

Serves the persisted message list for a chat id in AI SDK v6 ``UIMessage``
shape. Consumed by the frontend's ``fetchChatHistory`` on initial load.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.transport.http.deps import DBSession

router = APIRouter(tags=["chat"])


def _message_to_ui_message(
    *,
    id_: UUID,
    role: str,
    parts: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Convert a persisted row into an AI SDK v6 ``UIMessage``-shaped dict."""
    return {
        "id": str(id_),
        "role": role,
        "parts": parts,
        "metadata": metadata,
    }


@router.get(
    "/api/v1/chats/{chat_id}/messages",
    response_model=list[dict[str, Any]],
    responses={
        200: {
            "description": "Ordered list of UIMessages for the chat id (oldest first).",
        },
        400: {"description": "Malformed chat id"},
    },
)
async def list_chat_messages(
    chat_id: str,
    session: DBSession,
) -> list[dict[str, Any]]:
    """Return the chat's persisted messages as AI SDK v6 ``UIMessage[]``.

    Returns an empty list if the chat has no messages yet (including when
    the chat row itself doesn't exist — clients treat that as "fresh chat").
    """
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
            id_=row.id,
            role=row.role,
            parts=row.parts,
            metadata=row.metadata_,
        )
        for row in rows
    ]
