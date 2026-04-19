"""Fork a conversation at a chosen assistant message.

Duplicates messages up through the fork-point into a new ``Conversation`` row.
The new row carries ``parent_conversation_id`` + ``parent_message_id`` so the
sidebar can render the branching tree. No WDK strategy link, no gene-set
binding — a fork is a fresh exploration.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import Conversation, Message


class ForkError(ValueError):
    """Raised when the fork request references missing or unauthorized rows."""


async def fork_conversation(
    session: AsyncSession,
    *,
    source_conversation_id: UUID,
    from_message_id: UUID,
    user_id: UUID,
    new_name: str | None = None,
) -> Conversation:
    """Create a fork. ``from_message_id`` is the last message copied over."""
    source = await session.scalar(
        select(Conversation).where(Conversation.id == source_conversation_id),
    )
    if source is None or source.user_id != user_id:
        msg = "Source conversation not found"
        raise ForkError(msg)

    anchor = await session.scalar(
        select(Message).where(
            Message.id == from_message_id,
            Message.conversation_id == source_conversation_id,
        ),
    )
    if anchor is None:
        msg = "Fork anchor message not found in source conversation"
        raise ForkError(msg)

    prefix_rows = await session.scalars(
        select(Message)
        .where(
            Message.conversation_id == source_conversation_id,
            Message.created_at <= anchor.created_at,
        )
        .order_by(asc(Message.created_at)),
    )
    prefix = list(prefix_rows)

    new_conv_id = uuid4()
    fork = Conversation(
        id=new_conv_id,
        user_id=user_id,
        site_id=source.site_id,
        name=new_name or f"{source.name} (branch)",
        record_type=source.record_type,
        supervisor_model_id=source.supervisor_model_id,
        parent_conversation_id=source_conversation_id,
        parent_message_id=from_message_id,
    )
    session.add(fork)

    for src_msg in prefix:
        session.add(
            Message(
                id=uuid4(),
                conversation_id=new_conv_id,
                role=src_msg.role,
                parts=list(src_msg.parts),
                metadata_=dict(src_msg.metadata_ or {}),
            ),
        )

    await session.flush()
    return fork
