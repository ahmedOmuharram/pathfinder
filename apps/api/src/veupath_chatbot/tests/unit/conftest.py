"""Shared fixtures for unit tests."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.persistence.models import User
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.platform.errors import ErrorCode, ValidationError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks


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


# ---------------------------------------------------------------------------
# Step creation stubs (shared by test_step_creation_push + _service)
# ---------------------------------------------------------------------------


def make_step_graph(graph_id: str = "g1", site_id: str = "plasmodb") -> StrategyGraph:
    """Build a minimal StrategyGraph for testing."""
    return StrategyGraph(graph_id, "test", site_id)


def noop_validation_error_payload(exc: ValidationError) -> JSONObject:
    """Simple validation error → tool_error converter for tests."""
    return tool_error(ErrorCode.VALIDATION_ERROR, exc.title, detail=exc.detail)


async def resolve_record_type_stub(
    record_type: str | None,
    search_name: str | None,
    *,
    require_match: bool = False,
    allow_fallback: bool = True,
) -> str | None:
    """Stub: returns the record type as-is, or ``'transcript'`` as default."""
    return record_type or "transcript"


async def find_record_type_hint_stub(
    search_name: str, exclude: str | None = None
) -> str | None:
    """Stub: always returns None (no record-type hint)."""
    return None


def extract_vocab_options_stub(vocabulary: JSONObject) -> list[str]:
    """Stub: always returns an empty list."""
    return []


def make_step_creation_callbacks() -> ValidationCallbacks:
    """Build a ValidationCallbacks with stub implementations for step creation tests."""
    return ValidationCallbacks(
        resolve_record_type_for_search=resolve_record_type_stub,
        find_record_type_hint=find_record_type_hint_stub,
        extract_vocab_options=extract_vocab_options_stub,
        validation_error_payload=noop_validation_error_payload,
    )
