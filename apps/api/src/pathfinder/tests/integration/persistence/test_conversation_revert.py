from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

import pathfinder.persistence.session as session_module
from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.scratchpad.models import NoteCreate
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.persistence.models import (
    Conversation,
    ConversationEvent,
    Message,
    User,
)
from pathfinder.platform.config import get_settings
from pathfinder.services.conversations.revert import (
    RevertError,
    revert_conversation_to_message,
)


@pytest.fixture(scope="module", autouse=True)
async def _langgraph_checkpoint_tables(
    patch_app_db_engine: None,
) -> AsyncIterator[None]:
    del patch_app_db_engine
    async with lifespan_checkpointer(get_settings().database_url):
        yield


@pytest.fixture(autouse=True)
async def _truncate_langgraph_tables() -> AsyncIterator[None]:
    yield
    async with session_module.async_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE checkpoints, checkpoint_blobs, "
                "checkpoint_writes RESTART IDENTITY",
            ),
        )
        await session.commit()


async def _seed_user() -> User:
    async with session_module.async_session_factory() as session:
        user = User(id=uuid4(), external_id=f"u{uuid4()}")
        session.add(user)
        await session.commit()
        return user


async def _seed_conversation(user_id: UUID) -> Conversation:
    async with session_module.async_session_factory() as session:
        row = Conversation(
            user_id=user_id, site_id="plasmodb", name="", experiment_id=None,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def _seed_message(conv_id: UUID, role: str, text_body: str) -> Message:
    async with session_module.async_session_factory() as session:
        msg = Message(
            id=uuid4(),
            conversation_id=conv_id,
            role=role,
            parts=[{"type": "text", "text": text_body}],
            metadata_={},
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def _seed_checkpoint(thread_id: UUID, ts: datetime, cid: str) -> None:
    async with session_module.async_session_factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO checkpoints
                  (thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, metadata)
                VALUES
                  (:tid, '', :cid, 'test',
                   jsonb_build_object('v', 1, 'ts', CAST(:ts AS text), 'id', CAST(:cid AS text)),
                   '{}'::jsonb)
                """,
            ),
            {"tid": str(thread_id), "cid": cid, "ts": ts.isoformat()},
        )
        await session.commit()


class TestRevertConversation:
    async def test_deletes_messages_at_and_after_target(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        t1 = await _seed_message(conv.id, "user", "one")
        t2 = await _seed_message(conv.id, "assistant", "reply one")
        t3 = await _seed_message(conv.id, "user", "two")
        await _seed_message(conv.id, "assistant", "reply two")

        async with session_module.async_session_factory() as session:
            await revert_conversation_to_message(
                session,
                conversation_id=conv.id,
                target_message_id=t3.id,
                user_id=user.id,
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            remaining = (
                await session.scalars(
                    select(Message).where(Message.conversation_id == conv.id),
                )
            ).all()
        assert {m.id for m in remaining} == {t1.id, t2.id}

    async def test_deletes_scratchpad_notes_at_and_after_target(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        t1 = await _seed_message(conv.id, "user", "one")

        async with session_module.async_session_factory() as session:
            repo = ScratchpadRepository(session)
            pre = await repo.create(
                conversation_id=conv.id,
                data=NoteCreate(title="before", summary="s", body="b"),
            )
            await session.commit()

        t2 = await _seed_message(conv.id, "user", "two")

        async with session_module.async_session_factory() as session:
            repo = ScratchpadRepository(session)
            post = await repo.create(
                conversation_id=conv.id,
                data=NoteCreate(title="after", summary="s", body="b"),
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            await revert_conversation_to_message(
                session,
                conversation_id=conv.id,
                target_message_id=t2.id,
                user_id=user.id,
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            repo = ScratchpadRepository(session)
            notes = await repo.list_notes(conversation_id=conv.id, limit=50)
        ids = {n.id for n in notes}
        assert pre.id in ids
        assert post.id not in ids
        assert t1.role == "user"

    async def test_deletes_conversation_events_at_and_after_target(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        t1 = await _seed_message(conv.id, "user", "one")

        async with session_module.async_session_factory() as session:
            session.add(
                ConversationEvent(
                    conversation_id=conv.id,
                    chunk={"type": "data-pre"},
                    emitted_at=t1.created_at,
                ),
            )
            await session.commit()

        t2 = await _seed_message(conv.id, "user", "two")

        async with session_module.async_session_factory() as session:
            session.add(
                ConversationEvent(
                    conversation_id=conv.id,
                    chunk={"type": "data-post"},
                    emitted_at=datetime.now(UTC),
                ),
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            await revert_conversation_to_message(
                session,
                conversation_id=conv.id,
                target_message_id=t2.id,
                user_id=user.id,
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            remaining = (
                await session.scalars(
                    select(ConversationEvent).where(
                        ConversationEvent.conversation_id == conv.id,
                    ),
                )
            ).all()
        assert {e.chunk["type"] for e in remaining} == {"data-pre"}

    async def test_deletes_checkpoints_at_and_after_target(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        t1 = await _seed_message(conv.id, "user", "one")
        await _seed_checkpoint(conv.id, t1.created_at, f"{0:032d}")
        t2 = await _seed_message(conv.id, "user", "two")
        await _seed_checkpoint(conv.id, t2.created_at, f"{1:032d}")

        async with session_module.async_session_factory() as session:
            await revert_conversation_to_message(
                session,
                conversation_id=conv.id,
                target_message_id=t2.id,
                user_id=user.id,
            )
            await session.commit()

        async with session_module.async_session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT checkpoint_id FROM checkpoints "
                        "WHERE thread_id = :tid",
                    ),
                    {"tid": str(conv.id)},
                )
            ).all()
        assert [r[0] for r in rows] == [f"{0:032d}"]

    async def test_wrong_user_raises(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        t1 = await _seed_message(conv.id, "user", "one")

        async with session_module.async_session_factory() as session:
            with pytest.raises(RevertError):
                await revert_conversation_to_message(
                    session,
                    conversation_id=conv.id,
                    target_message_id=t1.id,
                    user_id=uuid4(),
                )

    async def test_target_not_found_raises(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        async with session_module.async_session_factory() as session:
            with pytest.raises(RevertError):
                await revert_conversation_to_message(
                    session,
                    conversation_id=conv.id,
                    target_message_id=uuid4(),
                    user_id=user.id,
                )

    async def test_assistant_message_target_rejected(self) -> None:
        user = await _seed_user()
        conv = await _seed_conversation(user.id)
        await _seed_message(conv.id, "user", "one")
        t2 = await _seed_message(conv.id, "assistant", "reply")

        async with session_module.async_session_factory() as session:
            with pytest.raises(RevertError):
                await revert_conversation_to_message(
                    session,
                    conversation_id=conv.id,
                    target_message_id=t2.id,
                    user_id=user.id,
                )
