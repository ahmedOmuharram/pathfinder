from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents._instructions import pinned_scratchpad
from pathfinder.ai.graph.nodes import _render_supervisor_state
from pathfinder.ai.graph.runtime import AgentDeps, Context, DBSessionFactory
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.scratchpad import tools as sc_tools
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.persistence.models import Conversation, User
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def conv_id(db_session: AsyncSession, seed_user: User) -> UUID:
    conv = Conversation(
        user_id=seed_user.id, site_id="plasmodb", name="", experiment_id=None,
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv.id


def _ctx(
    *, conv_id: UUID, db_session_factory: DBSessionFactory,
) -> RunContext[AgentDeps]:
    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=StrategySession(site_id="plasmodb"),
        conversation_id=conv_id,
        db_session_factory=db_session_factory,
    )
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_name="",
        tool_call_id="tc-1",
    )


async def test_empty_renders_empty_state(
    db_session: AsyncSession,
    db_session_factory: DBSessionFactory,
    conv_id: UUID,
) -> None:
    del db_session
    ctx = _ctx(conv_id=conv_id, db_session_factory=db_session_factory)
    out = await pinned_scratchpad(ctx)
    assert out is not None
    assert "empty" in out.lower()


async def test_populated_includes_titles(
    db_session: AsyncSession,
    db_session_factory: DBSessionFactory,
    conv_id: UUID,
) -> None:
    del db_session
    ctx = _ctx(conv_id=conv_id, db_session_factory=db_session_factory)
    await sc_tools.note(ctx, title="FINDING_ONE", summary="s", body="b")
    await sc_tools.note(ctx, title="FINDING_TWO", summary="s", body="b")
    out = await pinned_scratchpad(ctx)
    assert out is not None
    assert "FINDING_ONE" in out
    assert "FINDING_TWO" in out


async def test_supervisor_state_includes_scratchpad(
    db_session: AsyncSession,
    db_session_factory: DBSessionFactory,
    conv_id: UUID,
    seed_user: User,
) -> None:
    del db_session
    ctx = _ctx(conv_id=conv_id, db_session_factory=db_session_factory)
    await sc_tools.note(ctx, title="SUPERVISOR_SEES_ME", summary="s", body="b")

    state = PipelineState(
        conversation_id=conv_id,
        user_id=seed_user.id,
        site_id="plasmodb",
        mode="strategy",
    )
    runtime_context = Context(
        site_id="plasmodb",
        user_id=seed_user.id,
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=db_session_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    block = await _render_supervisor_state(state, runtime_context)
    assert "SUPERVISOR_SEES_ME" in block
