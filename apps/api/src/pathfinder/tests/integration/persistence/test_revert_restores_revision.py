"""A revert leaves the strategy the surviving transcript describes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import assistant_core.platform.db as session_module
import pytest
from assistant_core.conversation.checkpointer import lifespan_checkpointer
from assistant_core.persistence.models import Conversation, Message
from sqlalchemy import text

from pathfinder.persistence.models import ConversationStrategy, User
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.conversation_update import ConversationUpdate
from pathfinder.persistence.repositories.strategy_revision import (
    StrategyRevisionRepository,
)
from pathfinder.platform.config import get_settings
from pathfinder.services.conversations.revert import revert_conversation_to_message
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


async def _seed_thread() -> tuple[UUID, UUID]:
    user_id, conversation_id = uuid4(), uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="protease work",
            ),
        )
        await session.commit()
    return user_id, conversation_id


async def _add_message(conversation_id: UUID, role: str) -> UUID:
    message_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(
            Message(id=message_id, conversation_id=conversation_id, role=role),
        )
        await session.commit()
    return message_id


async def _write_strategy(conversation_id: UUID, step_ids: dict[str, int]) -> None:
    ast = (
        three_step_ast(dict(step_ids))
        if len(step_ids) == 3
        else four_step_ast(dict(step_ids))
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


async def test_revert_past_a_build_puts_the_strategy_back(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    """The card measured a four-step AST surviving the revert that deleted it."""
    del patch_app_db_engine, db_cleaner
    user_id, conversation_id = await _seed_thread()
    await _add_message(conversation_id, "user")
    await _write_strategy(conversation_id, _THREE)
    await _add_message(conversation_id, "assistant")
    turn_three_user = await _add_message(conversation_id, "user")
    await _write_strategy(conversation_id, _FOUR)
    await _add_message(conversation_id, "assistant")

    async with session_module.async_session_factory() as session:
        await revert_conversation_to_message(
            session,
            conversation_id=conversation_id,
            target_message_id=turn_three_user,
            user_id=user_id,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        strategy = await session.get(ConversationStrategy, conversation_id)
        assert strategy is not None
        assert strategy.step_count == 3
        assert strategy.strategy_ast["wdkStepIds"] == _THREE
        assert "stepCounts" not in strategy.strategy_ast
        latest = await StrategyRevisionRepository(session).latest(conversation_id)
        assert latest is not None
        assert latest.step_count == 3


async def test_revert_to_the_first_message_clears_a_strategy_built_after_it(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    """No snapshot precedes the target, so the thread had no strategy then."""
    del patch_app_db_engine, db_cleaner
    user_id, conversation_id = await _seed_thread()
    first_user = await _add_message(conversation_id, "user")
    await _write_strategy(conversation_id, _THREE)
    await _add_message(conversation_id, "assistant")

    async with session_module.async_session_factory() as session:
        await revert_conversation_to_message(
            session,
            conversation_id=conversation_id,
            target_message_id=first_user,
            user_id=user_id,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        strategy = await session.get(ConversationStrategy, conversation_id)
        assert strategy is not None
        assert strategy.step_count == 0
        assert strategy.record_type is None
        assert strategy.wdk_strategy_id is None
        assert strategy.strategy_ast == {}


async def test_revert_leaves_a_thread_without_history_alone(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    """A thread built before the revision store keeps what it has."""
    del patch_app_db_engine, db_cleaner
    user_id, conversation_id = await _seed_thread()
    first_user = await _add_message(conversation_id, "user")
    await _write_strategy(conversation_id, _THREE)
    await _add_message(conversation_id, "assistant")
    async with session_module.async_session_factory() as session:
        await StrategyRevisionRepository(session).delete_newer_than(
            conversation_id,
            revision_row_id=None,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        await revert_conversation_to_message(
            session,
            conversation_id=conversation_id,
            target_message_id=first_user,
            user_id=user_id,
        )
        await session.commit()

    async with session_module.async_session_factory() as session:
        strategy = await session.get(ConversationStrategy, conversation_id)
        assert strategy is not None
        assert strategy.step_count == 3
