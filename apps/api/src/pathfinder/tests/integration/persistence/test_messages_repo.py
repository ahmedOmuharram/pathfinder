from uuid import uuid4

import pathfinder.persistence.session as session_module
from pathfinder.persistence.models import Chat, User
from pathfinder.persistence.repositories.message import MessagesRepository


async def test_insert_and_fetch_message(
    patch_app_db_engine: None, db_cleaner: None
) -> None:
    """A single insert round-trips parts + metadata as JSONB."""
    del patch_app_db_engine, db_cleaner
    chat_id = uuid4()
    user_id = uuid4()
    message_id = uuid4()
    parts: list[dict[str, object]] = [
        {"type": "text", "text": "hello", "state": "done"},
    ]
    metadata: dict[str, object] = {
        "phase": "scoping",
        "model": "anthropic:claude-sonnet-4-5",
    }

    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(Chat(id=chat_id, user_id=user_id))
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
