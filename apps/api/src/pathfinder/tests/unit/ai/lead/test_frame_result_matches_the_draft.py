"""FRAME cannot report more than the draft records.

``FrameResult`` is three free fields, so a pass that called no tool could still
return ``spec_ready``. The Lead then reported a framed strategy over a spec
with no criteria and asked the user to re-describe what it already had.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.deltas import FrameResult
from pathfinder.ai.lead.sub_agent_dispatch import frame_work_order, run_frame
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.operational_spec import Criterion
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps() -> LeadDeps:
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


def _stub_stream(
    monkeypatch: Any,
    result: FrameResult,
    *,
    binds: bool = False,
) -> None:
    async def _fake(**kwargs: Any) -> FrameResult:
        if binds:
            agent_deps: AgentDeps = kwargs["agent_deps"]
            agent_deps.agent_state.operational_spec_draft.criteria.append(
                Criterion(id="c1", text="kinases", search_name="GenesByText")
            )
        return result

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _fake)


async def test_spec_ready_over_an_empty_draft_is_a_retry(monkeypatch: Any) -> None:
    _stub_stream(monkeypatch, FrameResult(disposition="spec_ready", summary="done"))

    with pytest.raises(ModelRetry) as excinfo:
        await run_frame(
            deps=_deps(),
            parent_tool_call_id="t1",
            work_order=frame_work_order("frame it", ""),
        )

    message = str(excinfo.value)
    assert "set_criterion" in message
    assert "set_structure" in message
    assert "drop_criterion" in message


async def test_spec_ready_with_one_bound_criterion_passes(monkeypatch: Any) -> None:
    delta = FrameResult(disposition="spec_ready", summary="bound one")
    _stub_stream(monkeypatch, delta, binds=True)
    deps = _deps()

    result = await run_frame(
        deps=deps, parent_tool_call_id="t1", work_order=frame_work_order("frame it", "")
    )

    assert result == delta
    assert deps.state.domain.operational_spec is not None


async def test_second_empty_result_becomes_needs_user(monkeypatch: Any) -> None:
    _stub_stream(monkeypatch, FrameResult(disposition="spec_ready", summary="done"))
    deps = _deps()

    with pytest.raises(ModelRetry):
        await run_frame(
            deps=deps,
            parent_tool_call_id="t1",
            work_order=frame_work_order("frame it", ""),
        )
    result = await run_frame(
        deps=deps, parent_tool_call_id="t2", work_order=frame_work_order("again", "")
    )

    assert isinstance(result, FrameResult)
    assert result.disposition == "needs_user"
    assert "no bound criterion" in result.summary


async def test_a_needs_user_result_over_an_empty_draft_is_not_a_retry(
    monkeypatch: Any,
) -> None:
    delta = FrameResult(disposition="needs_user", summary="which dataset?")
    _stub_stream(monkeypatch, delta)

    result = await run_frame(
        deps=_deps(),
        parent_tool_call_id="t1",
        work_order=frame_work_order("frame it", ""),
    )

    assert result == delta


async def test_an_exhausted_budget_still_reports_the_draft(monkeypatch: Any) -> None:
    async def _fake(**kwargs: Any) -> None:
        del kwargs

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _fake)

    result = await run_frame(
        deps=_deps(),
        parent_tool_call_id="t1",
        work_order=frame_work_order("frame it", ""),
    )

    assert isinstance(result, FrameResult)
    assert result.disposition == "needs_user"
    assert "budget" in result.summary
