"""Shared fixtures for unit tests."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.persistence.models import User
from pathfinder.persistence.repositories import ConversationRepository


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    async with session_maker() as session:
        yield session


@pytest.fixture
async def conv_repo(
    db_session: AsyncSession,
) -> ConversationRepository:
    return ConversationRepository(db_session)


@pytest.fixture
async def user_id(db_session: AsyncSession) -> UUID:
    """Create a User row and return its id."""
    uid = uuid4()
    db_session.add(User(id=uid))
    await db_session.flush()
    return uid


def populate_graph(graph: StrategyGraph, *steps: StrategyStepNode) -> None:
    """Add steps to graph bypassing single-root invariant for test setup."""
    for step in steps:
        graph.steps.update(flatten_tree(step))
    graph.recompute_roots()
