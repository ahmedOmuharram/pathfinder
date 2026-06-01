from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

import pathfinder.platform.db as session_module
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.persistence.models import Conversation, ConversationEvent, User


@pytest.mark.asyncio
async def test_writer_persists_and_notifies(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    conv_id = uuid4()
    turn_id = uuid4()

    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conv_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()

    writer = ChatEventWriter(conversation_id=conv_id, turn_id=turn_id)
    event_id = await writer.write(
        {"type": "text-delta", "id": "a", "delta": "hi"},
    )
    assert event_id > 0

    async with session_module.async_session_factory() as session:
        rows = (
            await session.scalars(
                select(ConversationEvent)
                .where(ConversationEvent.conversation_id == conv_id)
                .order_by(ConversationEvent.id),
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].turn_id == turn_id
        assert rows[0].chunk == {"type": "text-delta", "id": "a", "delta": "hi"}
        assert rows[0].id == event_id
