"""The Lead can throw a strategy away, behind an approval the user answers.

``build_strategy`` refuses a thread that already has a strategy and
``edit_strategy`` only changes one, so "scrap this and start again" needs a
tool of its own.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.dispatch_messages import build_would_replace_the_strategy
from pathfinder.ai.lead.lead_agent import build_lead_agent, clear_strategy
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.toolsets import execution
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.sync_state import WDKSyncState
from pathfinder.tests._support.sub_agents import toolset_tool_names


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _ctx() -> RunContext[LeadDeps]:
    session = StrategySession(site_id="plasmodb")
    graph = StrategyGraph(graph_id="g1", name="Kinases", site_id="plasmodb")
    graph.record_type = "transcript"
    graph.steps = flatten_tree(
        StrategyStepNode(id="step_a", search_name="GenesByText"),
    )
    graph.recompute_roots()
    session.graph = graph
    session.sync_state = WDKSyncState(
        wdk_step_ids={"step_a": 100},
        wdk_strategy_id=555,
    )
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="scrap this and start again",
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=state.user_id,
        strategy_session=session,
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    deps = LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        messages=[],
        tool_call_id="call_clear",
    )


def _no_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.conversation."
        "persist_strategy_ast_to_conversation",
        _noop,
    )


def test_the_lead_registers_the_clear_tool_behind_an_approval() -> None:
    tools = build_lead_agent()._function_toolset.tools

    assert "clear_strategy" in tools
    assert tools["clear_strategy"].requires_approval is True


def test_the_recovery_sub_agent_cannot_clear_the_strategy() -> None:
    """One destructive door, and the Lead holds it."""
    assert "clear_strategy" not in toolset_tool_names(execution.build_toolset())


async def test_clearing_empties_the_strategy_the_lead_can_see(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_persist(monkeypatch)
    ctx = _ctx()

    returned = await clear_strategy(ctx, confirm=True)

    graph = ctx.deps.runtime.strategy_session.get_graph(None)
    assert graph is not None
    assert graph.steps == {}
    assert ctx.deps.runtime.strategy_session.sync_state.wdk_strategy_id is None
    assert returned.return_value.graph_id == "g1"


async def test_clearing_without_confirmation_is_a_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_persist(monkeypatch)
    ctx = _ctx()

    with pytest.raises(ModelRetry):
        await clear_strategy(ctx, confirm=False)

    graph = ctx.deps.runtime.strategy_session.get_graph(None)
    assert graph is not None
    assert sorted(graph.steps) == ["step_a"]


def test_the_build_refusal_names_the_tool_that_starts_over() -> None:
    assert "clear_strategy" in build_would_replace_the_strategy(3)


def test_the_lead_instructions_name_the_tool_that_starts_over() -> None:
    instructions = " ".join(LEAD_INSTRUCTIONS.split())
    assert "``clear_strategy``" in instructions
