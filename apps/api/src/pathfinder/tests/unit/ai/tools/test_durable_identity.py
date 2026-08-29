"""durable_tool needs an identity, not the whole of AgentDeps."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.durable import DurableIdentity
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


@pytest.fixture
def lead_deps() -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="find kinases",
        domain=StrategyDomainState(),
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])


def test_lead_deps_exposes_the_conversation_and_the_user(lead_deps: LeadDeps) -> None:
    assert lead_deps.conversation_id is not None
    assert lead_deps.user_id is not None


def test_lead_deps_conversation_id_comes_from_the_turn_state(
    lead_deps: LeadDeps,
) -> None:
    assert lead_deps.conversation_id == lead_deps.state.conversation_id


def test_lead_deps_user_id_comes_from_the_turn_context(lead_deps: LeadDeps) -> None:
    assert lead_deps.user_id == lead_deps.runtime.user_id


def test_lead_deps_user_id_is_not_the_state_copy(lead_deps: LeadDeps) -> None:
    """The turn context is the account the worker acts as."""
    assert lead_deps.runtime.user_id != lead_deps.state.user_id
    assert lead_deps.user_id != lead_deps.state.user_id


def test_lead_deps_satisfies_the_durable_identity_protocol(
    lead_deps: LeadDeps,
) -> None:
    identity: DurableIdentity = lead_deps
    assert identity.conversation_id is not None


def test_agent_deps_still_satisfies_the_durable_identity_protocol() -> None:
    deps = AgentDeps(
        site_id="plasmodb",
        user_id=uuid4(),
        conversation_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
    )
    identity: DurableIdentity = deps
    assert identity.user_id is not None
