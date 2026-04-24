from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

import pathfinder.persistence.session as session_module
from pathfinder.persistence.models import Conversation, Message, User
from pathfinder.persistence.repositories import MessagesRepository


@pytest.mark.asyncio
async def test_upsert_replaces_parts_and_metadata(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Second upsert for the same ``message_id`` replaces parts+metadata.

    Mirrors how the graph pipeline writes partial turn state at each phase.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    conversation_id = uuid4()
    message_id = uuid4()

    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        await MessagesRepository(session).upsert_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role="assistant",
            parts=[{"type": "data-phase-start", "data": {"phase": "scoping"}}],
            metadata={"usage": {"totalTokens": 100, "costUsd": "0.01"}},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        await MessagesRepository(session).upsert_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role="assistant",
            parts=[
                {"type": "data-phase-start", "data": {"phase": "scoping"}},
                {"type": "data-phase-start", "data": {"phase": "discovery"}},
            ],
            metadata={"usage": {"totalTokens": 250, "costUsd": "0.03"}},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        rows = (
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id),
            )
        ).all()
        assert len(rows) == 1, rows
        final = rows[0]
        assert final.id == message_id
        assert len(final.parts) == 2
        assert final.parts[1]["data"]["phase"] == "discovery"
        assert final.metadata_ == {
            "usage": {"totalTokens": 250, "costUsd": "0.03"},
        }


@pytest.mark.asyncio
async def test_sum_usage_reads_partial_turn_metadata(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """After a mid-turn failure, a partial upserted message still contributes
    to ``sum_usage_for_conversation`` — so the composer footer reflects the
    tokens the user is being charged for.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    conversation_id = uuid4()
    message_id = uuid4()

    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        await repo.upsert_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role="assistant",
            parts=[{"type": "data-phase-start", "data": {"phase": "scoping"}}],
            metadata={"usage": {"totalTokens": 517, "costUsd": "0.042"}},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        total_tokens, total_cost = await MessagesRepository(
            session,
        ).sum_usage_for_conversation(conversation_id)
        assert total_tokens == 517
        assert str(total_cost) == "0.042"


@pytest.mark.asyncio
async def test_insert_message_is_idempotent_on_same_id(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Re-POSTing the same user message id (from a double-clicked Send,
    a network retry, or AI SDK resume) must not crash with a
    UniqueViolationError. The second insert is a no-op — the row's
    original parts and metadata stay intact (we don't want a retry to
    silently overwrite a turn's persisted state)."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    conversation_id = uuid4()
    message_id = uuid4()

    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()

    original_parts = [{"type": "text", "text": "find Plasmodium kinases"}]
    original_meta = {"siteId": "plasmodb", "mode": "strategy"}

    async with session_module.async_session_factory() as session:
        await MessagesRepository(session).insert_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role="user",
            parts=original_parts,
            metadata=original_meta,
        )
        await session.commit()

    # Second insert with the SAME id but different parts — must succeed
    # silently. The user double-clicked Send; the original turn is the
    # source of truth.
    async with session_module.async_session_factory() as session:
        await MessagesRepository(session).insert_message(
            message_id=message_id,
            conversation_id=conversation_id,
            role="user",
            parts=[{"type": "text", "text": "DIFFERENT TEXT"}],
            metadata={"siteId": "plasmodb", "mode": "different"},
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        rows = (
            await session.scalars(
                select(Message).where(Message.id == message_id),
            )
        ).all()
        assert len(rows) == 1
        kept = rows[0]
        # Original payload preserved — the second insert is a no-op,
        # not a clobber. (If clients want to update they use the upsert
        # path.)
        assert kept.parts == original_parts
        assert kept.metadata_ == original_meta
