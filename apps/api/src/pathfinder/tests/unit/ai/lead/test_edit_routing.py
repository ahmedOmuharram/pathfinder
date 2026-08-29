"""An edit turn is routed to the edit path, and a rebuild is refused.

``build_strategy`` replaces the whole strategy, which loses every WDK step id
and every value the researcher set by hand. It is not what an edit asks for.
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
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.edit_dispatch import run_edit
from pathfinder.ai.lead.sub_agent_dispatch import build_strategy
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _spec() -> OperationalSpec:
    return OperationalSpec(
        goal="proteases",
        criteria=[
            Criterion(
                id="step_text",
                text="protease text",
                search_name="GenesByText",
                role="seed",
                resolved_params={"organism": MultiPickValue(values=["Plasmodium"])},
            ),
            Criterion(id="step_go", text="proteolysis GO", search_name="GenesByGoTerm"),
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="step_text"),
                    StructureNode(kind="leaf", criterion_id="step_go"),
                ],
            )
        ),
    )


def _root() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_join",
        search_name=COMBINE_SEARCH_NAME,
        operator=CombineOp.INTERSECT,
        primary_input=StrategyStepNode(id="step_text", search_name="GenesByText"),
        secondary_input=StrategyStepNode(id="step_go", search_name="GenesByGoTerm"),
    )


def _ctx(*, with_strategy: bool) -> RunContext[LeadDeps]:
    session = StrategySession(site_id="plasmodb")
    if with_strategy:
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
        graph.record_type = "transcript"
        graph.steps = flatten_tree(_root())
        graph.recompute_roots()
        session.graph = graph
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="use P. vivax for the GO criterion",
        domain=StrategyDomainState(operational_spec=_spec()),
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
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


async def test_build_strategy_dispatch_refuses_a_non_empty_strategy() -> None:
    with pytest.raises(ModelRetry) as excinfo:
        await build_strategy(_ctx(with_strategy=True))

    message = str(excinfo.value)
    assert "edit_strategy" in message
    assert "ask the user first" in message
    # A camelCase name in a retry sends the model round a loop it cannot exit.
    assert "editStrategy" not in message


async def test_build_strategy_still_materializes_an_empty_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_build(**kwargs: Any) -> BuildOutcome:
        return BuildOutcome(pushed_step_ids=[kwargs["root"].id])

    monkeypatch.setattr(sub_agent_dispatch, "build_strategy_from_spec", _fake_build)

    result = await build_strategy(_ctx(with_strategy=False))

    assert result.outcome.pushed_step_ids


async def test_an_edit_on_a_thread_with_no_strategy_keeps_the_framed_spec() -> None:
    """A misrouted edit is a retry, and it destroys nothing the turn framed."""
    ctx = _ctx(with_strategy=False)
    ctx.deps.state.domain.spec_before_turn = None

    with pytest.raises(ModelRetry) as excinfo:
        await run_edit(deps=ctx.deps, parent_tool_call_id="t1", reason="edit it")

    assert "frame_problem" in str(excinfo.value)
    spec = ctx.deps.state.domain.operational_spec
    assert spec is not None
    assert {c.id for c in spec.criteria} == {"step_text", "step_go"}


def test_the_lead_is_told_to_route_an_edit_to_the_edit_tool() -> None:
    instructions = " ".join(LEAD_INSTRUCTIONS.split())
    assert "edit_strategy" in instructions
    assert (
        "call ``edit_strategy`` and NEVER ``frame_problem`` + ``build_strategy``"
        in instructions
    )
