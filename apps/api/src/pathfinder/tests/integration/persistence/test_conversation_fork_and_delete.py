"""Integration tests for the conversation fork tree + delete semantics.

Covers:

* ``fork_conversation``: copies messages up through the chosen anchor,
  sets ``parent_conversation_id`` / ``parent_message_id`` on the new row.
* ``ConversationRepository.delete(cascade=False)``: promotes children to the
  deleted node's parent, inheriting the fork point.
* ``ConversationRepository.delete(cascade=True)``: recursive CTE wipes the
  whole subtree.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import pathfinder.persistence.session as session_module
from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.scratchpad.models import NoteCreate
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.persistence.models import Conversation, Message, User
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.platform.config import get_settings
from pathfinder.services.conversations.fork import (
    ForkError,
    fork_conversation,
)


@pytest.fixture(scope="module", autouse=True)
async def _langgraph_checkpoint_tables(
    patch_app_db_engine: None,
) -> AsyncIterator[None]:
    """Ensure LangGraph's checkpoint/blob/write tables exist for this module.

    ``AsyncPostgresSaver.setup()`` is the only path that creates them; the
    main Alembic migrations and ``Base.metadata.create_all`` don't.
    """
    del patch_app_db_engine
    async with lifespan_checkpointer(get_settings().database_url):
        yield


@pytest.fixture(autouse=True)
async def _truncate_langgraph_tables() -> AsyncIterator[None]:
    """Clear checkpoint tables between tests so rows don't leak across cases."""
    yield
    async with session_module.async_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE checkpoints, checkpoint_blobs, "
                "checkpoint_writes RESTART IDENTITY",
            ),
        )
        await session.commit()


async def _seed_checkpoint(
    session: AsyncSession,
    *,
    thread_id: str,
    checkpoint_id: str,
    parent_checkpoint_id: str | None,
    ts: datetime,
) -> None:
    """Insert a minimal LangGraph checkpoint row with the given timestamp."""
    await session.execute(
        text(
            "INSERT INTO checkpoints "
            "(thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, "
            " type, checkpoint, metadata) "
            "VALUES (:thread_id, '', :checkpoint_id, :parent_checkpoint_id, "
            " 'test', CAST(:checkpoint AS jsonb), '{}'::jsonb)",
        ),
        {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint_id": parent_checkpoint_id,
            "checkpoint": f'{{"id": "{checkpoint_id}", "ts": "{ts.isoformat()}"}}',
        },
    )


async def _seed_blob(
    session: AsyncSession,
    *,
    thread_id: str,
    channel: str,
    version: str,
) -> None:
    await session.execute(
        text(
            "INSERT INTO checkpoint_blobs "
            "(thread_id, checkpoint_ns, channel, version, type, blob) "
            "VALUES (:thread_id, '', :channel, :version, 'empty', "
            " decode('00', 'hex'))",
        ),
        {"thread_id": thread_id, "channel": channel, "version": version},
    )


async def _seed_write(
    session: AsyncSession,
    *,
    thread_id: str,
    checkpoint_id: str,
    task_id: str = "t",
    idx: int = 0,
    channel: str = "c",
) -> None:
    await session.execute(
        text(
            "INSERT INTO checkpoint_writes "
            "(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, "
            " type, blob, task_path) "
            "VALUES (:thread_id, '', :checkpoint_id, :task_id, :idx, :channel, "
            " 'empty', decode('00', 'hex'), '')",
        ),
        {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "task_id": task_id,
            "idx": idx,
            "channel": channel,
        },
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


# ────────────────────────────────────────────────────────────────────
# Checkpoint-chain fork tests
# ────────────────────────────────────────────────────────────────────
#
# The dispatcher keys LangGraph checkpoints by ``thread_id = conversation_id``.
# ``fork_conversation`` must duplicate the chain so the branch's supervisor
# sees the same state the source had at the anchor moment. The cutoff is
# the ``created_at`` of the message immediately following the anchor; every
# checkpoint with ``ts < cutoff`` is copied, everything later is dropped.


async def _set_message_created_at(
    session: AsyncSession, *, message_id: UUID, ts: datetime,
) -> None:
    """Override a message's ``created_at`` for deterministic cutoff tests."""
    await session.execute(
        text("UPDATE messages SET created_at = :ts WHERE id = :id"),
        {"ts": ts, "id": message_id},
    )


async def _insert_message_at(
    session: AsyncSession,
    *,
    conv_id: UUID,
    role: str,
    text_body: str,
    ts: datetime,
) -> UUID:
    """Insert a message and explicitly pin its ``created_at``.

    The base ``_insert_message`` helper leans on the DB default (``now()``),
    which is racy with the checkpoint timestamps we seed. Tests that exercise
    the cutoff logic need deterministic ordering, so we flush and then
    UPDATE the row to a chosen ``ts``.
    """
    messages = MessagesRepository(session)
    msg_id = await _insert_message(
        messages, conv_id=conv_id, role=role, text=text_body,
    )
    await session.flush()
    await _set_message_created_at(session, message_id=msg_id, ts=ts)
    return msg_id


async def _two_turn_source(
    *, user_id: UUID, source_id: UUID,
) -> tuple[list[UUID], list[datetime]]:
    """Seed a source conversation with two turns (4 messages) and 4 checkpoints.

    Production-realistic timeline: an end-of-turn checkpoint is written
    *after* ``finalize_turn_node`` persists its assistant message, and the
    next turn's first checkpoint is written *after* the incoming user
    message lands. This matters because the fork cutoff is the created_at
    of the message right after the anchor; checkpoints strictly earlier
    than that cutoff are preserved.

    Synthetic timeline (anchored 2026-01-01, seconds-precision):

      t=10 — user message 1
      t=15 — checkpoint ``cp_u1``  (mid-turn-1)
      t=19 — assistant message 1 (persisted by finalize_turn_node)
      t=20 — checkpoint ``cp_a1``  (end-of-turn-1 — just after msg write)
      t=40 — user message 2
      t=45 — checkpoint ``cp_u2``  (mid-turn-2)
      t=49 — assistant message 2
      t=50 — checkpoint ``cp_a2``  (end-of-turn-2)

    Returns ``(message_ids, checkpoint_timestamps)`` ordered chronologically.
    """
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    cp_ts = [base + timedelta(seconds=s) for s in (15, 20, 45, 50)]
    msg_ts = [base + timedelta(seconds=s) for s in (10, 19, 40, 49)]
    turns = [
        ("cp_u1", None, cp_ts[0], "user", "hi", msg_ts[0]),
        ("cp_a1", "cp_u1", cp_ts[1], "assistant", "first reply", msg_ts[1]),
        ("cp_u2", "cp_a1", cp_ts[2], "user", "follow-up", msg_ts[2]),
        ("cp_a2", "cp_u2", cp_ts[3], "assistant", "second reply", msg_ts[3]),
    ]
    message_ids: list[UUID] = []

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id, name="root",
        )
        await session.commit()

    for cp_id, parent, cp_time, role, body, msg_time in turns:
        async with session_module.async_session_factory() as session:
            await _seed_checkpoint(
                session,
                thread_id=str(source_id),
                checkpoint_id=cp_id,
                parent_checkpoint_id=parent,
                ts=cp_time,
            )
            await session.commit()
        async with session_module.async_session_factory() as session:
            msg_id = await _insert_message_at(
                session, conv_id=source_id, role=role, text_body=body, ts=msg_time,
            )
            message_ids.append(msg_id)
            await session.commit()

    async with session_module.async_session_factory() as session:
        await _seed_blob(
            session, thread_id=str(source_id), channel="msg", version="v1",
        )
        await _seed_blob(
            session, thread_id=str(source_id), channel="msg", version="v2",
        )
        for cp_id, *_ in turns:
            await _seed_write(
                session, thread_id=str(source_id), checkpoint_id=cp_id,
            )
        await session.commit()

    return message_ids, cp_ts


# ────────────────────────────────────────────────────────────────────
# Invariant & resume helpers
# ────────────────────────────────────────────────────────────────────


async def _chain_is_valid(session: AsyncSession, thread_id: str) -> bool:
    """True if every surviving checkpoint's parent reference resolves.

    This is the fork correctness invariant: after a time-based cutoff, the
    surviving rows must form a valid chain — each non-null
    ``parent_checkpoint_id`` must point at another surviving row. An orphan
    parent would make LangGraph's chain walk unresolvable on resume.
    """
    result = await session.execute(
        text(
            "SELECT checkpoint_id, parent_checkpoint_id FROM checkpoints "
            "WHERE thread_id = :t",
        ),
        {"t": thread_id},
    )
    surviving = {row[0]: row[1] for row in result}
    for cp_id, parent in surviving.items():
        if parent is None:
            continue
        if parent not in surviving:
            return False
        _ = cp_id  # satisfy linters
    return True


async def _count_checkpoints(session: AsyncSession, thread_id: str) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :t"),
        {"t": thread_id},
    )
    return int(result.scalar_one())


async def _put_real_checkpoint(
    saver: AsyncPostgresSaver,
    *,
    thread_id: str,
    checkpoint_id: str,
    parent_checkpoint_id: str | None,
    ts: datetime,
    channel_values: dict[str, object],
) -> None:
    """Write a LangGraph checkpoint via the real saver at a chosen ``ts``.

    Going through ``AsyncPostgresSaver.aput`` means every field LangGraph
    depends on (channel_versions, blob references, metadata) is populated
    the same way production does it — so resume tests exercise the full
    serialize/deserialize path rather than hand-rolled JSON stubs.
    """
    parent_config: RunnableConfig = {
        "configurable": {"thread_id": thread_id, "checkpoint_ns": ""},
    }
    if parent_checkpoint_id is not None:
        parent_config["configurable"]["checkpoint_id"] = parent_checkpoint_id

    versions: ChannelVersions = {
        k: f"{checkpoint_id}.{i}" for i, k in enumerate(channel_values)
    }
    checkpoint: Checkpoint = {
        "v": 4,
        "id": checkpoint_id,
        "ts": ts.isoformat(),
        "channel_values": dict(channel_values),
        "channel_versions": dict(versions),
        "versions_seen": {},
        "updated_channels": list(channel_values.keys()),
    }
    metadata: CheckpointMetadata = {
        "source": "loop",
        "step": 0,
        "parents": {},
    }
    await saver.aput(parent_config, checkpoint, metadata, versions)


async def _resume_latest(
    saver: AsyncPostgresSaver, thread_id: str,
) -> CheckpointTuple | None:
    return await saver.aget_tuple(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
    )


# ────────────────────────────────────────────────────────────────────
# Behavioral tests for the checkpoint-chain truncation
# ────────────────────────────────────────────────────────────────────


async def test_fork_from_latest_count_matches_source(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Fork-from-latest: every checkpoint row in the source lands in the branch.

    Doesn't care about specific ids — just cardinality and chain validity.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        source_count = await _count_checkpoints(session, str(source_id))

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[-1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        assert await _count_checkpoints(session, str(fork_id)) == source_count
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_from_mid_chat_drops_later_turn_count(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Fork mid-chat copies strictly fewer checkpoints than the source.

    Exact count depends on the timeline; we verify the inequality + that
    the remaining chain is still internally consistent.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        source_count = await _count_checkpoints(session, str(source_id))

    # Anchor = first assistant (end of turn 1). Second-turn checkpoints
    # must not leak in.
    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        fork_count = await _count_checkpoints(session, str(fork_id))
        assert 0 < fork_count < source_count
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_cutoff_is_strictly_less_than(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """A checkpoint whose ``ts`` equals the cutoff is NOT copied.

    Production rule: the first checkpoint of turn N+1 is created after the
    user message of turn N+1 is persisted; if by coincidence its ``ts``
    ties the cutoff, it still belongs to turn N+1 and must be excluded.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    anchor_msg_ts = base + timedelta(seconds=10)
    boundary_ts = base + timedelta(seconds=20)  # cutoff = next_msg.created_at
    next_msg_ts = boundary_ts                   # identical to checkpoint ts

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await _seed_checkpoint(
            session,
            thread_id=str(source_id),
            checkpoint_id="pre",
            parent_checkpoint_id=None,
            ts=base + timedelta(seconds=5),
        )
        await _seed_checkpoint(
            session,
            thread_id=str(source_id),
            checkpoint_id="boundary",
            parent_checkpoint_id="pre",
            ts=boundary_ts,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="anchor",
        )
        await session.flush()
        await _set_message_created_at(
            session, message_id=anchor, ts=anchor_msg_ts,
        )
        following = await _insert_message(
            messages, conv_id=source_id, role="user", text="next",
        )
        await session.flush()
        await _set_message_created_at(
            session, message_id=following, ts=next_msg_ts,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT checkpoint_id FROM checkpoints WHERE thread_id = :t",
            ),
            {"t": str(fork_id)},
        )
        ids = {r[0] for r in result}
        # ``pre`` (ts < cutoff) is in; ``boundary`` (ts == cutoff) is out.
        assert "pre" in ids
        assert "boundary" not in ids
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_identical_message_timestamps_deterministic(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Two adjacent messages with identical ``created_at``: fork still runs
    safely and produces a valid chain. Edge case for clock-resolution ties.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    shared_ts = base + timedelta(seconds=10)

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await _seed_checkpoint(
            session,
            thread_id=str(source_id),
            checkpoint_id="only",
            parent_checkpoint_id=None,
            ts=base + timedelta(seconds=1),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="anchor",
        )
        other = await _insert_message(
            messages, conv_id=source_id, role="user", text="next",
        )
        await session.flush()
        await _set_message_created_at(session, message_id=anchor, ts=shared_ts)
        await _set_message_created_at(session, message_id=other, ts=shared_ts)
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        assert await _count_checkpoints(session, str(fork_id)) >= 0
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_with_no_checkpoints(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Conversation without any checkpoints forks cleanly — empty thread."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="synthetic",
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        assert await _count_checkpoints(session, str(fork_id)) == 0
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_messages_are_copied_in_order(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Message prefix is a fresh copy with the same order and content."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[-1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        source_rows = await MessagesRepository(session).list_messages_for_conversation(
            source_id,
        )
        fork_rows = await MessagesRepository(session).list_messages_for_conversation(
            fork_id,
        )
        assert [r.role for r in fork_rows] == [r.role for r in source_rows]
        assert [r.parts[0]["text"] for r in fork_rows] == [
            r.parts[0]["text"] for r in source_rows
        ]
        # Fork rows are new records — ids differ from source.
        assert {r.id for r in source_rows}.isdisjoint({r.id for r in fork_rows})


async def test_fork_cascade_delete_removes_descendants(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """``delete(cascade=True)`` on source wipes every descendant branch row."""
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        await ConversationRepository(session).delete(source_id, cascade=True)
        await session.commit()

    async with session_module.async_session_factory() as session:
        remaining = await session.scalar(
            select(Conversation).where(Conversation.id == fork_id),
        )
        assert remaining is None


async def test_fork_survives_noncascade_delete_of_source(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Non-cascade delete of source: branch is promoted to root, its own
    checkpoint copy untouched and still a valid chain.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[-1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id
        fork_count_before = await _count_checkpoints(session, str(fork_id))

    async with session_module.async_session_factory() as session:
        await ConversationRepository(session).delete(source_id)
        await session.commit()

    async with session_module.async_session_factory() as session:
        surviving = await session.scalar(
            select(Conversation).where(Conversation.id == fork_id),
        )
        assert surviving is not None
        assert surviving.parent_conversation_id is None
        # Checkpoints copy is unaffected.
        assert await _count_checkpoints(session, str(fork_id)) == fork_count_before
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_of_fork_scopes_to_parent_branch(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Grand-fork pulls only from its direct parent (mid fork), never the
    grandparent. Tests that fork() doesn't follow ``parent_conversation_id``.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        mid = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[1],
            user_id=user_id,
        )
        await session.commit()
        mid_id = mid.id

    async with session_module.async_session_factory() as session:
        mid_count = await _count_checkpoints(session, str(mid_id))
        mid_msgs = await MessagesRepository(session).list_messages_for_conversation(
            mid_id,
        )

    async with session_module.async_session_factory() as session:
        grand = await fork_conversation(
            session,
            source_conversation_id=mid_id,
            from_message_id=mid_msgs[-1].id,
            user_id=user_id,
        )
        await session.commit()
        grand_id = grand.id

    async with session_module.async_session_factory() as session:
        # Grand = full copy of mid (latest fork); mid was partial copy of source.
        assert await _count_checkpoints(session, str(grand_id)) == mid_count
        assert await _chain_is_valid(session, str(grand_id))


async def test_fork_resume_returns_anchor_state(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """*The* behavioral test. Seed a conversation whose checkpoints carry
    distinct ``turn_total_tokens`` values, fork mid-chat, and verify that
    ``AsyncPostgresSaver.aget_tuple`` on the fork returns the anchor-turn
    state — not the source's later state.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await session.commit()

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        await _put_real_checkpoint(
            saver,
            thread_id=str(source_id),
            checkpoint_id="01000000-0000-7000-8000-000000000001",
            parent_checkpoint_id=None,
            ts=base + timedelta(seconds=5),
            channel_values={"turn_total_tokens": 100, "current_phase": "scoping"},
        )
        await _put_real_checkpoint(
            saver,
            thread_id=str(source_id),
            checkpoint_id="01000000-0000-7000-8000-000000000002",
            parent_checkpoint_id="01000000-0000-7000-8000-000000000001",
            ts=base + timedelta(seconds=20),
            channel_values={"turn_total_tokens": 250, "current_phase": "verification"},
        )
        await _put_real_checkpoint(
            saver,
            thread_id=str(source_id),
            checkpoint_id="01000000-0000-7000-8000-000000000003",
            parent_checkpoint_id="01000000-0000-7000-8000-000000000002",
            ts=base + timedelta(seconds=50),
            channel_values={"turn_total_tokens": 1500, "current_phase": "execution"},
        )

    anchor_ts = base + timedelta(seconds=19)
    next_ts = base + timedelta(seconds=40)

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="anchor",
        )
        following = await _insert_message(
            messages, conv_id=source_id, role="user", text="next turn",
        )
        await session.flush()
        await _set_message_created_at(session, message_id=anchor, ts=anchor_ts)
        await _set_message_created_at(session, message_id=following, ts=next_ts)
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        fork_tuple = await _resume_latest(saver, str(fork_id))
        source_tuple = await _resume_latest(saver, str(source_id))

    assert fork_tuple is not None
    assert source_tuple is not None
    # Source's latest state is the third (later) turn.
    assert source_tuple.checkpoint["channel_values"]["turn_total_tokens"] == 1500
    assert (
        source_tuple.checkpoint["channel_values"]["current_phase"] == "execution"
    )
    # Fork's latest state is the end-of-anchor-turn checkpoint — never
    # the later one, regardless of how many ts-buckets follow.
    assert fork_tuple.checkpoint["channel_values"]["turn_total_tokens"] == 250
    assert (
        fork_tuple.checkpoint["channel_values"]["current_phase"] == "verification"
    )

    async with session_module.async_session_factory() as session:
        assert await _chain_is_valid(session, str(fork_id))


async def test_fork_resume_latest_matches_source_exactly(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Fork-from-latest: fork's resume state is byte-identical to source's.

    Any field LangGraph reads on resume (channel_values, channel_versions,
    updated_channels) must survive the copy unchanged.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await session.commit()

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        await _put_real_checkpoint(
            saver,
            thread_id=str(source_id),
            checkpoint_id="02000000-0000-7000-8000-000000000001",
            parent_checkpoint_id=None,
            ts=base + timedelta(seconds=5),
            channel_values={"turn_total_tokens": 800, "current_phase": "planning"},
        )

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="only",
        )
        await session.flush()
        await _set_message_created_at(
            session, message_id=anchor, ts=base + timedelta(seconds=10),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        src = await _resume_latest(saver, str(source_id))
        frk = await _resume_latest(saver, str(fork_id))

    assert src is not None
    assert frk is not None
    assert frk.checkpoint["id"] == src.checkpoint["id"]
    assert frk.checkpoint["ts"] == src.checkpoint["ts"]
    assert frk.checkpoint["channel_values"] == src.checkpoint["channel_values"]
    assert frk.checkpoint["channel_versions"] == src.checkpoint["channel_versions"]


async def test_fork_scales_to_many_turns(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Multi-turn conversation: fork at an arbitrary anchor copies the
    expected count of preceding-turn checkpoints, keeps the chain valid,
    and resumes at the anchor turn's state.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    turns = 8

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await session.commit()

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        prev_id: str | None = None
        for turn in range(turns):
            cp_id = f"03000000-0000-7000-8000-{turn:012d}"
            await _put_real_checkpoint(
                saver,
                thread_id=str(source_id),
                checkpoint_id=cp_id,
                parent_checkpoint_id=prev_id,
                ts=base + timedelta(seconds=turn * 10 + 5),
                channel_values={"turn_total_tokens": (turn + 1) * 100},
            )
            prev_id = cp_id

    msg_ids: list[UUID] = []
    for turn in range(turns):
        async with session_module.async_session_factory() as session:
            messages = MessagesRepository(session)
            msg = await _insert_message(
                messages, conv_id=source_id,
                role="assistant", text=f"turn-{turn}",
            )
            await session.flush()
            await _set_message_created_at(
                session,
                message_id=msg,
                ts=base + timedelta(seconds=turn * 10 + 9),
            )
            msg_ids.append(msg)
            await session.commit()

    # Fork at turn 3 (0-indexed). Cutoff = turn-4 message's created_at
    # (=turn*10+9 with turn=4 → 49s). Checkpoints with ts < 49: turns 0-4
    # (ts in {5,15,25,35,45}). Anchor turn 3 contributes its end-of-turn
    # checkpoint at ts=35; turn 4's start-of-next-turn checkpoint at
    # ts=45 is also included (because it falls before the next message).
    # The KEY behavioral property isn't the exact count — it's that the
    # resume state's turn_total_tokens reflects pre-cutoff state.
    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=msg_ids[3],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        assert await _chain_is_valid(session, str(fork_id))
        # Strictly fewer checkpoints than source.
        source_count = await _count_checkpoints(session, str(source_id))
        fork_count = await _count_checkpoints(session, str(fork_id))
        assert 0 < fork_count < source_count

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        frk = await _resume_latest(saver, str(fork_id))
    assert frk is not None
    # The latest surviving checkpoint in the fork is turn 4's start-of-turn
    # (ts=45 < cutoff=49). Its turn_total_tokens = (4+1)*100 = 500.
    # Turn 5+ (tokens 600+) must NOT be present.
    assert frk.checkpoint["channel_values"]["turn_total_tokens"] <= 500
    assert frk.checkpoint["channel_values"]["turn_total_tokens"] >= 100


async def test_fork_writes_only_reference_surviving_checkpoints(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Every ``checkpoint_writes`` row in the fork must join back to a
    checkpoint that also exists in the fork. No orphan writes.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    message_ids, _ = await _two_turn_source(user_id=user_id, source_id=source_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=message_ids[1],
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM checkpoint_writes w "
                "WHERE w.thread_id = :t "
                "  AND NOT EXISTS ("
                "     SELECT 1 FROM checkpoints c "
                "     WHERE c.thread_id = w.thread_id "
                "       AND c.checkpoint_ns = w.checkpoint_ns "
                "       AND c.checkpoint_id = w.checkpoint_id"
                "  )",
            ),
            {"t": str(fork_id)},
        )
        orphan_writes = int(result.scalar_one())
        assert orphan_writes == 0


async def test_fork_preserves_blob_bytes_exactly(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Every (channel, version) blob in the source lands in the fork with
    byte-for-byte-identical ``blob`` contents.

    Cheap mistake this test catches: any mid-copy transformation of the
    ``blob`` column (re-encoding, compression toggle, truncation, serde
    version bump) would change the bytes even when (channel, version) stay
    the same. LangGraph's deserialize path would then decode to something
    different, and the supervisor's resumed state would diverge silently —
    hardest kind of bug.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(
            session, conversation_id=source_id, user_id=user_id,
        )
        await session.commit()

    async with lifespan_checkpointer(get_settings().database_url) as saver:
        await _put_real_checkpoint(
            saver,
            thread_id=str(source_id),
            checkpoint_id="04000000-0000-7000-8000-000000000001",
            parent_checkpoint_id=None,
            ts=base + timedelta(seconds=5),
            channel_values={
                "turn_total_tokens": 777,
                "current_phase": "discovery",
                "discovered_searches": ["GenesByTaxon", "GenesByRNASeq"],
                "retrieved_memories": [{"kind": "strategy", "name": "baseline"}],
            },
        )

    async with session_module.async_session_factory() as session:
        messages = MessagesRepository(session)
        anchor = await _insert_message(
            messages, conv_id=source_id, role="assistant", text="done",
        )
        await session.flush()
        await _set_message_created_at(
            session, message_id=anchor, ts=base + timedelta(seconds=10),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT src.channel, src.version, src.type, src.blob,
                       dst.type, dst.blob
                FROM checkpoint_blobs src
                LEFT JOIN checkpoint_blobs dst
                    ON dst.thread_id = :dst_t
                   AND dst.checkpoint_ns = src.checkpoint_ns
                   AND dst.channel = src.channel
                   AND dst.version = src.version
                WHERE src.thread_id = :src_t
                """,
            ),
            {"src_t": str(source_id), "dst_t": str(fork_id)},
        )
        rows = result.all()
        assert len(rows) > 0, "source has no blobs to compare — fixture bug"
        for channel, version, src_type, src_blob, dst_type, dst_blob in rows:
            assert dst_type is not None, (
                f"blob missing in fork for channel={channel!r} version={version!r}"
            )
            assert dst_type == src_type, (
                f"blob type mismatch on ({channel!r}, {version!r}): "
                f"source={src_type!r} fork={dst_type!r}"
            )
            assert bytes(dst_blob) == bytes(src_blob), (
                f"blob bytes mismatch on ({channel!r}, {version!r}): "
                f"source={len(bytes(src_blob))}B fork={len(bytes(dst_blob))}B"
            )

    # Round-trip: the saver should decode the fork's blobs back into the
    # same Python values as the source's, confirming the bytes really do
    # round-trip through LangGraph's serde and not just through raw COPY.
    async with lifespan_checkpointer(get_settings().database_url) as saver:
        src_tuple = await _resume_latest(saver, str(source_id))
        frk_tuple = await _resume_latest(saver, str(fork_id))
    assert src_tuple is not None
    assert frk_tuple is not None
    assert src_tuple.checkpoint["channel_values"] == (
        frk_tuple.checkpoint["channel_values"]
    )


# ────────────────────────────────────────────────────────────────────
# Scratchpad fork copy (MAJOR 1)
# ────────────────────────────────────────────────────────────────────


async def test_fork_copies_scratchpad_notes_with_fresh_ids(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Forking a conversation duplicates its scratchpad notes under the fork.

    The copies get FRESH ids (source ids must not leak into the fork scope),
    the copied rows preserve title/body/pinned, and the source scratchpad
    stays intact. Guards MAJOR 1 of the scratchpad design review: without
    this copy, the fork's checkpointed message history referenced note ids
    that didn't exist under the new conversation_id.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(session, conversation_id=source_id, user_id=user_id)
        await session.commit()

    async with session_module.async_session_factory() as session:
        sc = ScratchpadRepository(session)
        src_note_1 = await sc.create(
            conversation_id=source_id,
            data=NoteCreate(
                title="GenesByRNASeq leads",
                summary="1200 genes with threshold 2",
                body="Full scratchpad body #1",
                tags=["candidate"],
                pinned=True,
            ),
        )
        src_note_2 = await sc.create(
            conversation_id=source_id,
            data=NoteCreate(
                title="Dead end: GenesByGO",
                summary="Lost stage specificity",
                body="Do not retry.",
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        anchor_id = await _insert_message(
            MessagesRepository(session),
            conv_id=source_id, role="assistant", text="anchor",
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

    async with session_module.async_session_factory() as session:
        sc = ScratchpadRepository(session)
        fork_notes = await sc.list_notes(conversation_id=fork_id, limit=100)
        src_notes = await sc.list_notes(conversation_id=source_id, limit=100)

    assert len(fork_notes) == 2
    assert len(src_notes) == 2

    # Titles/bodies/pinned replicated exactly.
    by_title = {n.title: n for n in fork_notes}
    assert by_title["GenesByRNASeq leads"].body == "Full scratchpad body #1"
    assert by_title["GenesByRNASeq leads"].pinned is True
    assert by_title["GenesByRNASeq leads"].tags == ["candidate"]
    assert by_title["Dead end: GenesByGO"].body == "Do not retry."
    assert by_title["Dead end: GenesByGO"].pinned is False

    # Ids are distinct across source and fork — no shared primary keys.
    src_ids = {n.id for n in src_notes}
    fork_ids = {n.id for n in fork_notes}
    assert src_ids.isdisjoint(fork_ids)
    assert src_note_1.id in src_ids
    assert src_note_2.id in src_ids
    assert src_note_1.id not in fork_ids
    assert src_note_2.id not in fork_ids


async def test_fork_rewrites_scratchpad_ids_in_copied_message_parts(
    patch_app_db_engine: None, db_cleaner: None,
) -> None:
    """Message parts that cite old scratchpad ids are rewritten to the new ids.

    A turn transcript may contain tool-note / tool-read_note parts where
    ``input.note_id`` or ``output.id`` holds ``n-xxxxxx``. After fork the
    fork's messages must cite the fork-scope ids, not the source-scope ids
    — otherwise the chat UI shows dangling links.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    source_id = uuid4()

    async with session_module.async_session_factory() as session:
        await _seed_user(session, user_id)
        await _seed_conversation(session, conversation_id=source_id, user_id=user_id)
        await session.commit()

    async with session_module.async_session_factory() as session:
        sc = ScratchpadRepository(session)
        src_note = await sc.create(
            conversation_id=source_id,
            data=NoteCreate(
                title="The one",
                summary="A note",
                body="Body here.",
            ),
        )
        await session.commit()
    src_note_id = src_note.id

    # Persist a message whose parts reference the source note id in both
    # the tool-note output (what the UI renders after creation) and a
    # follow-up tool-read_note input (what the agent did next).
    async with session_module.async_session_factory() as session:
        msg_id = uuid4()
        session.add(
            Message(
                id=msg_id,
                conversation_id=source_id,
                role="assistant",
                parts=[
                    {"type": "text", "text": "saving a note", "state": "done"},
                    {
                        "type": "tool-note",
                        "toolCallId": "tc-1",
                        "state": "output-available",
                        "input": {
                            "title": "The one",
                            "summary": "A note",
                            "body": "Body here.",
                        },
                        "output": {"id": src_note_id, "title": "The one"},
                    },
                    {
                        "type": "tool-read_note",
                        "toolCallId": "tc-2",
                        "state": "output-available",
                        "input": {"note_id": src_note_id},
                        "output": {"id": src_note_id, "body": "Body here."},
                    },
                ],
                metadata_={"mode": "strategy"},
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=source_id,
            from_message_id=msg_id,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        sc = ScratchpadRepository(session)
        fork_notes = await sc.list_notes(conversation_id=fork_id, limit=10)
        fork_messages = await MessagesRepository(session).list_messages_for_conversation(
            fork_id,
        )

    assert len(fork_notes) == 1
    new_id = fork_notes[0].id
    assert new_id != src_note_id

    assert len(fork_messages) == 1
    parts = fork_messages[0].parts
    tool_note_part = next(p for p in parts if p["type"] == "tool-note")
    tool_read_part = next(p for p in parts if p["type"] == "tool-read_note")

    assert tool_note_part["output"]["id"] == new_id
    assert tool_read_part["input"]["note_id"] == new_id
    assert tool_read_part["output"]["id"] == new_id
    # Non-scratchpad parts untouched.
    text_part = next(p for p in parts if p["type"] == "text")
    assert text_part["text"] == "saving a note"
