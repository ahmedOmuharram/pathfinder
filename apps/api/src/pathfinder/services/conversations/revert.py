from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, DateTime, bindparam, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import (
    BackgroundTask,
    Conversation,
    ConversationEvent,
    Message,
    ScratchpadNote,
)
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


class RevertError(ValueError):
    """Raised when the revert request references missing or unauthorized rows."""


def _rows(result: object) -> int:
    return cast("CursorResult[object]", result).rowcount or 0


async def revert_conversation_to_message(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    target_message_id: UUID,
    user_id: UUID,
) -> None:
    conv = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id),
    )
    if conv is None or conv.user_id != user_id:
        logger.warning(
            "revert: conversation lookup failed",
            conversation_id=str(conversation_id),
            target_message_id=str(target_message_id),
            user_id=str(user_id),
            row_exists=conv is not None,
            owner_match=conv is not None and conv.user_id == user_id,
        )
        msg = "Conversation not found"
        raise RevertError(msg)

    target = await session.scalar(
        select(Message).where(
            Message.id == target_message_id,
            Message.conversation_id == conversation_id,
        ),
    )
    if target is None:
        wrong_conv_owner = await session.scalar(
            select(Message.conversation_id).where(
                Message.id == target_message_id,
            ),
        )
        logger.warning(
            "revert: target message not in conversation",
            conversation_id=str(conversation_id),
            target_message_id=str(target_message_id),
            message_belongs_to=(
                str(wrong_conv_owner)
                if wrong_conv_owner is not None
                else None
            ),
        )
        msg = "Target message not found"
        raise RevertError(msg)
    if target.role != "user":
        logger.warning(
            "revert: target is not user-authored",
            conversation_id=str(conversation_id),
            target_message_id=str(target_message_id),
            actual_role=target.role,
        )
        msg = "Can only revert to a user-authored message"
        raise RevertError(msg)

    cutoff_ts = target.created_at
    thread_id = str(conversation_id)

    deleted_messages = _rows(await session.execute(
        delete(Message).where(
            Message.conversation_id == conversation_id,
            Message.created_at >= cutoff_ts,
        ),
    ))
    deleted_notes = _rows(await session.execute(
        delete(ScratchpadNote).where(
            ScratchpadNote.conversation_id == conversation_id,
            ScratchpadNote.created_at >= cutoff_ts,
        ),
    ))
    deleted_events = _rows(await session.execute(
        delete(ConversationEvent).where(
            ConversationEvent.conversation_id == conversation_id,
            ConversationEvent.emitted_at >= cutoff_ts,
        ),
    ))
    deleted_tasks = _rows(await session.execute(
        delete(BackgroundTask).where(
            BackgroundTask.conversation_id == conversation_id,
            BackgroundTask.created_at >= cutoff_ts,
        ),
    ))

    writes_stmt = text(
        """
        DELETE FROM checkpoint_writes w
        USING checkpoints c
        WHERE w.thread_id = c.thread_id
          AND w.checkpoint_ns = c.checkpoint_ns
          AND w.checkpoint_id = c.checkpoint_id
          AND c.thread_id = :thread_id
          AND (c.checkpoint->>'ts')::timestamptz >= :cutoff
        """,
    ).bindparams(bindparam("cutoff", type_=DateTime(timezone=True)))
    deleted_writes = _rows(await session.execute(
        writes_stmt, {"thread_id": thread_id, "cutoff": cutoff_ts},
    ))

    checkpoints_stmt = text(
        """
        DELETE FROM checkpoints
        WHERE thread_id = :thread_id
          AND (checkpoint->>'ts')::timestamptz >= :cutoff
        """,
    ).bindparams(bindparam("cutoff", type_=DateTime(timezone=True)))
    deleted_checkpoints = _rows(await session.execute(
        checkpoints_stmt, {"thread_id": thread_id, "cutoff": cutoff_ts},
    ))

    logger.info(
        "conversation reverted to message",
        conversation_id=thread_id,
        target_message_id=str(target_message_id),
        deleted_messages=deleted_messages,
        deleted_notes=deleted_notes,
        deleted_events=deleted_events,
        deleted_tasks=deleted_tasks,
        deleted_checkpoints=deleted_checkpoints,
        deleted_checkpoint_writes=deleted_writes,
    )
