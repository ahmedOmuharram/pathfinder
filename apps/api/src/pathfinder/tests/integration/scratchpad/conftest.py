from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from langgraph.store.postgres.aio import AsyncPostgresStore
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from pathfinder.assistant_core.memory.lifespan import lifespan_memory_store
from pathfinder.persistence.models import User
from pathfinder.platform.db import DBSessionFactory


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as session:
        yield session


@pytest.fixture
def db_session_factory(
    session_maker: async_sessionmaker[AsyncSession],
) -> DBSessionFactory:
    return session_maker


@pytest.fixture
async def seed_user(db_session: AsyncSession) -> User:
    user = User(id=uuid4())
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


@pytest.fixture
async def memory_store(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncPostgresStore]:
    """Raw LangGraph ``AsyncPostgresStore`` bound to the test DB.

    Matches the shape assigned to ``AgentDeps.memory_store`` in production
    (the unwrapped store — :class:`MemoryStore` wraps it at tool call time).
    """
    del db_engine
    database_url = os.environ["DATABASE_URL"]
    async with lifespan_memory_store(database_url) as store:
        yield store
