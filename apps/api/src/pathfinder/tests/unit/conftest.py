"""Shared fixtures for unit tests."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.persistence.models import User
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.errors import ErrorCode, ValidationError
from pathfinder.platform.tool_errors import tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_validation import ValidationCallbacks


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


# ---------------------------------------------------------------------------
# Step creation stubs (shared by test_step_creation_push + _service)
# ---------------------------------------------------------------------------


def make_step_graph(graph_id: str = "g1", site_id: str = "plasmodb") -> StrategyGraph:
    """Build a minimal StrategyGraph for testing."""
    return StrategyGraph(graph_id, "test", site_id)


def populate_graph(graph: StrategyGraph, *steps: StrategyStepNode) -> None:
    """Add steps to graph bypassing single-root invariant for test setup."""
    for step in steps:
        graph.steps[step.id] = step
    graph.recompute_roots()


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


def make_step_creation_callbacks() -> ValidationCallbacks:
    """Build a ValidationCallbacks with stub implementations for step creation tests."""
    return ValidationCallbacks(
        resolve_record_type_for_search=resolve_record_type_stub,
        find_record_type_hint=find_record_type_hint_stub,
        validation_error_payload=noop_validation_error_payload,
    )
