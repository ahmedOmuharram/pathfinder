"""Integration tests for the conversation fork tree + delete semantics.

Covers:

* ``fork_conversation``: copies messages up through the chosen anchor,
  sets ``parent_conversation_id`` / ``parent_message_id`` on the new row.
* ``ConversationRepository.delete(cascade=False)``: promotes children to the
  deleted node's parent, inheriting the fork point.
* ``ConversationRepository.delete(cascade=True)``: recursive CTE wipes the
  whole subtree.
"""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pathfinder.persistence.session as session_module
from pathfinder.persistence.models import Conversation, Message, User
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.services.conversations.fork import (
    ForkError,
    fork_conversation,
)


async def _seed_user(session: AsyncSession, user_id: UUID) -> None:
    session.add(User(id=user_id))
    await session.flush()


async def _seed_conversation(
    session: AsyncSession, *, conversation_id: UUID, user_id: UUID, name: str = "root",
) -> None:
    session.add(
        Conversation(
            id=conversation_id, user_id=user_id, site_id="plasmodb", name=name,
        ),
    )
    await session.flush()


async def _insert_message(
    repo: MessagesRepository, *, conv_id: UUID, role: str, text: str,
) -> UUID:
    message_id = uuid4()
    await repo.insert_message(
        message_id=message_id,
        conversation_id=conv_id,
        role=role,
        parts=[{"type": "text", "text": text, "state": "done"}],
        metadata={"mode": "strategy"},
    )
    return message_id


async def test_fork_copies_prefix_and_sets_parent_refs(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(session, conversation_id=source_id, user_id=user_id)
        await session.commit()

    # Separate commits = distinct ``created_at`` per message. Matches production
    # where each turn writes a single message in its own transaction.
    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        await _insert_message(messages, conv_id=source_id, role="user", text="hi")
        await session.commit()

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor_id = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="first reply",
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        await _insert_message(messages, conv_id=source_id, role="user", text="follow-up")
        await session.commit()

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        await _insert_message(
            messages, conv_id=source_id, role="assistant", text="second reply",
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor_id,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id
        assert fork.parent_conversation_id == source_id
        assert fork.parent_message_id == anchor_id
        assert fork.site_id == "plasmodb"

    async with session_module.async_session_factory() as session:
        rows = await MessagesRepository(session).list_messages_for_conversation(fork_id)
        # Prefix = first user + first assistant = 2 messages.
        assert len(rows) == 2
        texts = [r.parts[0]["text"] for r in rows]
        assert texts == ["hi", "first reply"]


async def test_fork_rejects_unknown_source(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    async with session_module.async_session_factory() as session:
        try:
            await fork_conversation(
                session,
                source_conversation_id=uuid4(),
                from_message_id=uuid4(),
                user_id=uuid4(),
            )
        except ForkError:
            return
        msg = "expected ForkError for missing source"
        raise AssertionError(msg)


async def test_fork_rejects_wrong_owner(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    owner_id = uuid4()
    other_id = uuid4()
    source_id = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, owner_id)
        await _seed_user(session, other_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=owner_id,
        )
        anchor_id = await _insert_message(
            MessagesRepository(session),
            conv_id=source_id, role="assistant", text="x",
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        try:
            await fork_conversation(
                session,
                source_conversation_id=source_id,
                from_message_id=anchor_id,
                user_id=other_id,
            )
        except ForkError:
            return
        msg = "expected ForkError when caller doesn't own source"
        raise AssertionError(msg)


async def test_delete_non_cascade_promotes_children(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Deleting ``b`` in a→b→c chain moves ``c`` under ``a``."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    a_id, b_id, c_id = uuid4(), uuid4(), uuid4()
    anchor_msg = uuid4()
    fork_anchor = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(session, conversation_id=a_id, user_id=user_id, name="a")
        session.add(
            Message(
                id=anchor_msg,
                conversation_id=a_id,
                role="assistant",
                parts=[],
                metadata_={},
            ),
        )
        await session.flush()
        session.add(
            Conversation(
                id=b_id, user_id=user_id, site_id="plasmodb", name="b",
                parent_conversation_id=a_id, parent_message_id=anchor_msg,
            ),
        )
        await session.flush()
        session.add(
            Message(
                id=fork_anchor,
                conversation_id=b_id,
                role="assistant",
                parts=[],
                metadata_={},
            ),
        )
        await session.flush()
        session.add(
            Conversation(
                id=c_id, user_id=user_id, site_id="plasmodb", name="c",
                parent_conversation_id=b_id, parent_message_id=fork_anchor,
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = ConversationRepository(session)
        await repo.delete(b_id)
        await session.commit()

    async with session_module.async_session_factory() as session:
        c = await session.scalar(select(Conversation).where(Conversation.id == c_id))
        a_gone = await session.scalar(
            select(Conversation).where(Conversation.id == b_id),
        )
        assert a_gone is None
        assert c is not None
        assert c.parent_conversation_id == a_id
        # c inherits B's fork point in A, since B was B's link to A.
        assert c.parent_message_id == anchor_msg


async def test_delete_cascade_wipes_subtree(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    a_id, b_id, c_id, d_id = uuid4(), uuid4(), uuid4(), uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(session, conversation_id=a_id, user_id=user_id, name="a")
        session.add(
            Conversation(
                id=b_id, user_id=user_id, site_id="plasmodb", name="b",
                parent_conversation_id=a_id,
            ),
        )
        session.add(
            Conversation(
                id=c_id, user_id=user_id, site_id="plasmodb", name="c",
                parent_conversation_id=b_id,
            ),
        )
        session.add(
            Conversation(
                id=d_id, user_id=user_id, site_id="plasmodb", name="d",
                parent_conversation_id=c_id,
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = ConversationRepository(session)
        await repo.delete(b_id, cascade=True)
        await session.commit()

    async with session_module.async_session_factory() as session:
        remaining = (
            await session.scalars(
                select(Conversation.id).where(
                    Conversation.id.in_([a_id, b_id, c_id, d_id]),
                ),
            )
        ).all()
        assert set(remaining) == {a_id}


async def test_delete_root_non_cascade_promotes_children_to_roots(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Deleting root with cascade=False null-outs child's parent_* fields."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    root_id, child_id = uuid4(), uuid4()
    anchor_msg = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=root_id, user_id=user_id, name="root",
        )
        session.add(
            Message(
                id=anchor_msg,
                conversation_id=root_id,
                role="assistant",
                parts=[],
                metadata_={},
            ),
        )
        await session.flush()
        session.add(
            Conversation(
                id=child_id, user_id=user_id, site_id="plasmodb", name="child",
                parent_conversation_id=root_id,
                parent_message_id=anchor_msg,
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        repo = ConversationRepository(session)
        await repo.delete(root_id)
        await session.commit()

    async with session_module.async_session_factory() as session:
        child = await session.scalar(
            select(Conversation).where(Conversation.id == child_id),
        )
        assert child is not None
        assert child.parent_conversation_id is None
        assert child.parent_message_id is None
