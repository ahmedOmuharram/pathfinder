"""Targeted re-discovery on plan denial — dispatch-path integration.

Exercises the real ``discover_searches`` Lead dispatch tool (work-order
construction + ``_agent_deps`` seeding), mocking only the LLM boundary
(``_stream_sub_agent``). Asserts that ``keep_prior_selections=True``:
  (a) hands the discovery sub-agent a TARGETED RE-DISCOVERY work order, and
  (b) seeds the sub-agent with the already-selected searches (additive — the
      re-discovery does not start from an empty universe).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.deltas import DiscoveryDelta
from pathfinder.ai.lead.sub_agent_dispatch import discover_searches
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

pytestmark = pytest.mark.asyncio


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called here"
    raise AssertionError(msg)


def _stub_model() -> FunctionModel:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content="ok")])

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield "ok"

    return FunctionModel(_fn, stream_function=_stream, model_name="test")


def _interpro_selection() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByInterproDomain",
        display_name="InterPro domain genes",
        record_type="transcript",
        description="kinase via PFAM domain",
        parameter_names=["organism", "domain_database"],
        required_params=["organism"],
        selection_status="selected",
    )


def _lead_deps() -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        discovered_searches={"GenesByInterproDomain": _interpro_selection()},
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        phase_models={},
        phase_reasoning={},
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=runtime,
        retrieved_memories=[],
    )


async def test_keep_prior_selections_targets_and_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_stream(**kwargs: Any) -> DiscoveryDelta:
        captured["work_order"] = kwargs["work_order"]
        captured["agent_deps"] = kwargs["agent_deps"]
        return DiscoveryDelta(findings_summary="found a GO kinase search")

    monkeypatch.setattr(sub_agent_dispatch, "_stream_sub_agent", _fake_stream)

    deps = _lead_deps()
    ctx: RunContext[LeadDeps] = RunContext(
        deps=deps, model=_stub_model(), usage=RunUsage()
    )

    delta = await discover_searches(
        ctx,
        reason="plan denied: identify kinases by GO molecular function, not InterPro",
        intent_summary="find a GO molecular function kinase-activity search",
        hints="keep the signal-peptide search; replace the InterPro kinase step",
        keep_prior_selections=True,
    )

    assert isinstance(delta, DiscoveryDelta)
    assert "TARGETED RE-DISCOVERY" in captured["work_order"]
    assert "GO molecular function kinase-activity" in captured["work_order"]
    seeded: AgentDeps = captured["agent_deps"]
    assert "GenesByInterproDomain" in seeded.agent_state.discovered_searches
    assert (
        seeded.agent_state.discovered_searches["GenesByInterproDomain"].selection_status
        == "selected"
    )


async def test_default_discovery_has_no_targeted_directive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_stream(**kwargs: Any) -> DiscoveryDelta:
        captured["work_order"] = kwargs["work_order"]
        return DiscoveryDelta(findings_summary="ok")

    monkeypatch.setattr(sub_agent_dispatch, "_stream_sub_agent", _fake_stream)

    deps = _lead_deps()
    ctx: RunContext[LeadDeps] = RunContext(
        deps=deps, model=_stub_model(), usage=RunUsage()
    )

    await discover_searches(
        ctx,
        reason="initial discovery",
        intent_summary="find kinase searches",
    )

    assert "TARGETED RE-DISCOVERY" not in captured["work_order"]
