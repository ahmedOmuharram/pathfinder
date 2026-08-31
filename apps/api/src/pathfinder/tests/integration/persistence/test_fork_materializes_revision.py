"""A branch reproduces the thread as it stood at the branched message."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import assistant_core.platform.db as session_module
import pytest
from assistant_core.conversation.checkpointer import lifespan_checkpointer
from assistant_core.persistence.models import (
    Conversation,
    ConversationEvent,
    Message,
)
from assistant_core.platform.types import JSONObject
from sqlalchemy import func, select, text

from pathfinder.persistence.models import (
    BackgroundTask,
    ConversationStrategy,
    StrategyRevision,
    User,
)
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.conversation_update import ConversationUpdate
from pathfinder.platform.config import get_settings
from pathfinder.platform.errors import ErrorCode, ForkRefusedError
from pathfinder.services.conversations import fork_strategy
from pathfinder.services.conversations.fork import ForkError, fork_conversation
from pathfinder.services.conversations.revert import revert_conversation_to_message
from pathfinder.services.strategies.materialize import MaterializedStrategy
from pathfinder.tests.integration.persistence._strategy_shapes import (
    four_step_ast,
    three_step_ast,
)

_THREE = {"combine": 15, "protease": 13, "gameto": 14}
_FOUR = {"orthologs": 16, "combine": 15, "protease": 13, "gameto": 14}


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


@dataclass
class _FakePush:
    """Stands in for the WDK push, recording the tree it was handed."""

    new_wdk_strategy_id: int = 330534153
    seen: list[JSONObject] | None = None

    async def __call__(
        self,
        *,
        site_id: str,
        conversation_id: UUID,
        name: str,
        strategy_ast: JSONObject,
    ) -> MaterializedStrategy:
        del site_id, conversation_id, name
        if self.seen is None:
            self.seen = []
        self.seen.append(strategy_ast)
        steps = strategy_ast.get("wdkStepIds") or {}
        return MaterializedStrategy(
            strategy_ast=strategy_ast,
            record_type="transcript",
            step_count=3 if len(steps) == 3 else len(steps),
            wdk_strategy_id=self.new_wdk_strategy_id,
        )


def _install_fake_push(monkeypatch: pytest.MonkeyPatch) -> _FakePush:
    fake = _FakePush()
    monkeypatch.setattr(fork_strategy, "materialize_strategy_snapshot", fake)
    return fake


async def _seed_user() -> UUID:
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()
    return user_id


async def _seed_conversation(
    user_id: UUID,
    *,
    assistant_id: str = "pathfinder",
) -> UUID:
    conversation_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="protease work",
                assistant_id=assistant_id,
            ),
        )
        await session.commit()
    return conversation_id


async def _add_message(
    conversation_id: UUID,
    role: str,
    *,
    chunks: list[JSONObject],
) -> UUID:
    message_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(
            Message(id=message_id, conversation_id=conversation_id, role=role),
        )
        await session.flush()
        for chunk in chunks:
            session.add(
                ConversationEvent(
                    conversation_id=conversation_id,
                    turn_id=message_id,
                    chunk=chunk,
                ),
            )
        await session.commit()
    return message_id


async def _write_strategy(conversation_id: UUID, step_ids: dict[str, int]) -> None:
    ast = (
        three_step_ast(dict(step_ids))
        if len(step_ids) == 3
        else four_step_ast(
            dict(step_ids),
        )
    )
    async with session_module.async_session_factory() as session:
        await ConversationRepository(session).update_conversation(
            conversation_id,
            ConversationUpdate(
                strategy_ast=ast,
                record_type="transcript",
                step_count=len(step_ids),
                wdk_strategy_id=330423363,
                wdk_strategy_id_set=True,
            ),
        )
        await session.commit()


@dataclass(frozen=True)
class _FourTurns:
    conversation_id: UUID
    user_one: UUID
    answer_two: UUID
    user_three: UUID
    answer_four: UUID


async def _four_turn_thread(user_id: UUID) -> _FourTurns:
    """Turn 2 builds three steps; turn 4 adds an ortholog transform."""
    conversation_id = await _seed_conversation(user_id)
    user_one = await _add_message(
        conversation_id,
        "user",
        chunks=[
            {
                "type": "user-message",
                "message": {"id": "", "role": "user", "parts": []},
            },
        ],
    )
    await _stamp_user_chunk(conversation_id, user_one)
    await _write_strategy(conversation_id, _THREE)
    answer_two = await _add_message(
        conversation_id,
        "assistant",
        chunks=[{"type": "start", "messageId": ""}],
    )
    await _stamp_start_chunk(conversation_id, answer_two)
    user_three = await _add_message(
        conversation_id,
        "user",
        chunks=[
            {
                "type": "user-message",
                "message": {"id": "", "role": "user", "parts": []},
            },
        ],
    )
    await _stamp_user_chunk(conversation_id, user_three)
    await _write_strategy(conversation_id, _FOUR)
    answer_four = await _add_message(
        conversation_id,
        "assistant",
        chunks=[{"type": "start", "messageId": ""}],
    )
    await _stamp_start_chunk(conversation_id, answer_four)
    return _FourTurns(
        conversation_id=conversation_id,
        user_one=user_one,
        answer_two=answer_two,
        user_three=user_three,
        answer_four=answer_four,
    )


async def _stamp_user_chunk(conversation_id: UUID, message_id: UUID) -> None:
    await _stamp(conversation_id, message_id, key="message")


async def _stamp_start_chunk(conversation_id: UUID, message_id: UUID) -> None:
    await _stamp(conversation_id, message_id, key="messageId")


async def _stamp(conversation_id: UUID, message_id: UUID, *, key: str) -> None:
    async with session_module.async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(
                ConversationEvent.conversation_id == conversation_id,
                ConversationEvent.turn_id == message_id,
            )
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
        assert row is not None
        chunk = dict(row.chunk)
        if key == "message":
            chunk["message"] = {**chunk["message"], "id": str(message_id)}
        else:
            chunk["messageId"] = str(message_id)
        row.chunk = chunk
        await session.commit()


def _message_ids_in(chunk: JSONObject) -> set[str]:
    found: set[str] = set()
    raw = chunk.get("messageId")
    if isinstance(raw, str):
        found.add(raw)
    message = chunk.get("message")
    if isinstance(message, dict) and isinstance(message.get("id"), str):
        found.add(str(message["id"]))
    return found


async def test_branch_at_turn_two_gets_the_three_step_tree_and_a_new_wdk_id(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The card's measurement: the branch showed 4 steps and root 16."""
    del patch_app_db_engine, db_cleaner
    push = _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=thread.conversation_id,
            from_message_id=thread.answer_two,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    assert push.seen is not None
    assert push.seen[0]["wdkStepIds"] == _THREE
    async with session_module.async_session_factory() as session:
        strategy = await session.get(ConversationStrategy, fork_id)
        assert strategy is not None
        assert strategy.step_count == 3
        assert strategy.wdk_strategy_id == 330534153
        assert "orthologs" not in (strategy.strategy_ast.get("wdkStepIds") or {})


async def test_branch_before_the_build_has_no_strategy(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del patch_app_db_engine, db_cleaner
    push = _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=thread.conversation_id,
            from_message_id=thread.user_one,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    assert push.seen is None
    async with session_module.async_session_factory() as session:
        assert await session.get(ConversationStrategy, fork_id) is None


async def test_branch_of_a_thread_with_no_history_is_refused(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A thread built before the revision store cannot be reproduced."""
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)
    async with session_module.async_session_factory() as session:
        await session.execute(
            StrategyRevision.__table__.delete().where(
                StrategyRevision.conversation_id == thread.conversation_id,
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        with pytest.raises(ForkRefusedError) as excinfo:
            await fork_conversation(
                session,
                source_conversation_id=thread.conversation_id,
                from_message_id=thread.answer_two,
                user_id=user_id,
            )
    assert excinfo.value.code is ErrorCode.FORK_REFUSED
    assert excinfo.value.status == 409


async def test_branch_is_refused_while_a_durable_task_runs(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)
    async with session_module.async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=uuid4(),
                conversation_id=thread.conversation_id,
                user_id=user_id,
                tool_name="run_eda_compute",
                status="running",
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        with pytest.raises(ForkRefusedError):
            await fork_conversation(
                session,
                source_conversation_id=thread.conversation_id,
                from_message_id=thread.answer_four,
                user_id=user_id,
            )


async def test_a_branch_carries_no_parent_message_id_and_reverts_in_place(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The card's 404: the branch replayed the parent's ids."""
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)
    parent_ids = {
        str(thread.user_one),
        str(thread.answer_two),
        str(thread.user_three),
        str(thread.answer_four),
    }

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=thread.conversation_id,
            from_message_id=thread.answer_two,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ConversationEvent).where(
                        ConversationEvent.conversation_id == fork_id,
                    ),
                )
            )
            .scalars()
            .all()
        )
        chunk_ids: set[str] = set()
        for row in rows:
            chunk_ids |= _message_ids_in(row.chunk)
        fork_message_ids = {
            str(mid)
            for mid in (
                await session.execute(
                    select(Message.id).where(Message.conversation_id == fork_id),
                )
            ).scalars()
        }
    assert chunk_ids
    assert chunk_ids & parent_ids == set()
    assert chunk_ids <= fork_message_ids

    branch_user_message = next(mid for mid in chunk_ids if mid in fork_message_ids)
    async with session_module.async_session_factory() as session:
        target = await session.scalar(
            select(Message).where(
                Message.conversation_id == fork_id,
                Message.role == "user",
            ),
        )
        assert target is not None
        await revert_conversation_to_message(
            session,
            conversation_id=fork_id,
            target_message_id=target.id,
            user_id=user_id,
        )
        await session.commit()
    assert branch_user_message in fork_message_ids


async def test_a_fork_log_survives_a_parent_revert_and_delete(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The card's 5 -> 4: the parent's task row took the fork's chunk."""
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    thread = await _four_turn_thread(user_id)
    task_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=thread.conversation_id,
                user_id=user_id,
                tool_name="run_eda_compute",
                status="complete",
            ),
        )
        await session.flush()
        session.add(
            ConversationEvent(
                conversation_id=thread.conversation_id,
                task_id=task_id,
                chunk={"type": "data-task-progress", "data": {"percent": 50}},
            ),
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=thread.conversation_id,
            from_message_id=thread.answer_four,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    before = await _event_count(fork_id)
    assert before > 0

    async with session_module.async_session_factory() as session:
        await revert_conversation_to_message(
            session,
            conversation_id=thread.conversation_id,
            target_message_id=thread.user_three,
            user_id=user_id,
        )
        await session.commit()
    assert await _event_count(fork_id) == before

    async with session_module.async_session_factory() as session:
        await ConversationRepository(session).delete(thread.conversation_id)
        await session.commit()
    assert await _event_count(fork_id) == before


async def _event_count(conversation_id: UUID) -> int:
    async with session_module.async_session_factory() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(ConversationEvent)
                .where(ConversationEvent.conversation_id == conversation_id),
            )
        ) or 0


async def test_a_branch_of_a_site_help_thread_stays_site_help(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    conversation_id = await _seed_conversation(user_id, assistant_id="site_help")
    anchor = await _add_message(
        conversation_id,
        "assistant",
        chunks=[{"type": "start", "messageId": ""}],
    )
    await _stamp_start_chunk(conversation_id, anchor)

    async with session_module.async_session_factory() as session:
        fork = await fork_conversation(
            session,
            source_conversation_id=conversation_id,
            from_message_id=anchor,
            user_id=user_id,
        )
        await session.commit()
        fork_id = fork.id

    async with session_module.async_session_factory() as session:
        source = await session.get(Conversation, conversation_id)
        branch = await session.get(Conversation, fork_id)
        assert source is not None
        assert branch is not None
        assert branch.assistant_id == "site_help"
        assert branch.application_id == source.application_id


async def test_fork_still_rejects_an_anchor_from_another_thread(
    patch_app_db_engine: None,
    db_cleaner: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del patch_app_db_engine, db_cleaner
    _install_fake_push(monkeypatch)
    user_id = await _seed_user()
    conversation_id = await _seed_conversation(user_id)
    async with session_module.async_session_factory() as session:
        with pytest.raises(ForkError):
            await fork_conversation(
                session,
                source_conversation_id=conversation_id,
                from_message_id=uuid4(),
                user_id=user_id,
            )
