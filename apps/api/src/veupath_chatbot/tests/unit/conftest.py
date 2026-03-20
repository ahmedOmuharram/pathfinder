"""Shared fixtures for unit tests."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from veupath_chatbot.persistence.models import User
from veupath_chatbot.persistence.repositories.stream import StreamRepository


@pytest.fixture(autouse=True)
async def _unit_redis(redis_setup: None) -> None:
    """Ensure Redis is available for all unit tests.

    Many unit tests call production code that transitively hits get_redis()
    (e.g. event emission, orchestrator helpers). The container is session-scoped
    so this adds ~1ms per test for flushdb, not container startup.
    """


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    async with session_maker() as session:
        yield session


@pytest.fixture
async def stream_repo(
    db_session: AsyncSession,
) -> StreamRepository:
    return StreamRepository(db_session)


@pytest.fixture
async def user_id(db_session: AsyncSession) -> UUID:
    """Create a User row and return its id."""
    uid = uuid4()
    db_session.add(User(id=uid))
    await db_session.flush()
    return uid
