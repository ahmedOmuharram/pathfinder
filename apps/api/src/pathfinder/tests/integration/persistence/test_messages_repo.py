"""Integration tests for MessagesRepository (new parts-based schema).

These exercise the new `messages` table added alongside the legacy
`stream_projections` / `chat_messages` tables while the chat/SSE overhaul
(Task 3 of the pydantic-ai migration) is in progress. Once the overhaul
completes, the old tables get dropped and these tests stay as-is.
"""

from uuid import uuid4

import pathfinder.persistence.session as session_module
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories.message import MessagesRepository


async def test_insert_and_fetch_message(
    patch_app_db_engine: None, db_cleaner: None
) -> None:
    """A single insert round-trips parts + metadata as JSONB."""
    chat_id = uuid4()
    message_id = uuid4()
    parts: list[dict[str, object]] = [
        {"type": "text", "text": "hello", "state": "done"},
    ]
    metadata: dict[str, object] = {
        "phase": "scoping",
        "model": "anthropic:claude-sonnet-4-5",
    }

    async with session_module.async_session_factory() as session:
        session.add(Chat(id=chat_id))
        await session.flush()

        repo = MessagesRepository(session)
        await repo.insert_message(
            message_id=message_id,
            chat_id=chat_id,
            role="user",
            parts=parts,
            metadata=metadata,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        rows = await repo.list_messages_for_chat(chat_id)

    assert len(rows) == 1
    assert rows[0].id == message_id
    assert rows[0].chat_id == chat_id
    assert rows[0].role == "user"
    assert rows[0].parts == parts
    assert rows[0].metadata_ == metadata


async def test_upsert_message_in_progress(
    patch_app_db_engine: None, db_cleaner: None
) -> None:
    """Mid-stream checkpoints upsert on the message id — no duplicate rows."""
    chat_id = uuid4()
    message_id = uuid4()

    async with session_module.async_session_factory() as session:
        session.add(Chat(id=chat_id))
        await session.flush()

        repo = MessagesRepository(session)
        await repo.upsert_message(
            message_id=message_id,
            chat_id=chat_id,
            role="assistant",
            parts=[{"type": "text", "text": "hel", "state": "streaming"}],
            metadata={},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        await repo.upsert_message(
            message_id=message_id,
            chat_id=chat_id,
            role="assistant",
            parts=[{"type": "text", "text": "hello world", "state": "streaming"}],
            metadata={"phase": "execution"},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        rows = await repo.list_messages_for_chat(chat_id)

    assert len(rows) == 1, "upsert must not create a second row"
    assert rows[0].id == message_id
    assert rows[0].parts == [
        {"type": "text", "text": "hello world", "state": "streaming"},
    ]
    assert rows[0].metadata_ == {"phase": "execution"}
