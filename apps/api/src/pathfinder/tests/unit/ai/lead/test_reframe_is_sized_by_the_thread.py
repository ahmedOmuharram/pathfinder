"""A FRAME dispatch is never sized below what the thread already states.

A clarification that re-frames from a spec which bound nothing has no criteria
to count, so the model's declaration is all the sizing there was.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.deltas import FrameResult
from pathfinder.ai.lead.sub_agent_dispatch import frame_work_order, run_frame
from pathfinder.ai.lead.sub_agent_stream import PhaseRun
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec
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
        user_prompt="Find the kinases.",
    )
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
    )


@pytest.fixture
def declared_sizes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The size every dispatch runs at, in dispatch order."""
    sizes: list[int] = []

    async def _capture(*, run: PhaseRun, **kwargs: object) -> None:
        del kwargs
        sizes.append(run.declared_criteria)

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _capture)
    return sizes


def _requirement(kind: ConstraintKind, label: str, value: str) -> Constraint:
    return Constraint(
        kind=kind,
        label=label,
        requested_value=value,
        source=ConstraintSource.USER_EXPLICIT,
    )


@pytest.mark.asyncio
async def test_a_declaration_below_the_thread_is_raised_to_it(
    declared_sizes: list[int],
) -> None:
    deps = _deps()
    deps.state.domain.spec_before_turn = OperationalSpec(
        goal="find the kinases",
        criteria=[Criterion(id=f"c{i}", text=f"criterion {i}") for i in range(8)],
    )

    result = await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("re-frame after the clarification", "kinases"),
        expected_criteria=3,
    )

    assert isinstance(result, FrameResult)
    assert declared_sizes == [8]


@pytest.mark.asyncio
async def test_the_requirements_the_thread_states_are_the_floor(
    declared_sizes: list[int],
) -> None:
    deps = _deps()
    deps.state.domain.requirements = [
        _requirement(ConstraintKind.ORGANISM, "organism", "Plasmodium falciparum"),
        _requirement(ConstraintKind.DATA_TYPE, "expression dataset", "trophozoite"),
        _requirement(ConstraintKind.PERCENTILE, "high expression", "top 10%"),
        _requirement(ConstraintKind.STATISTICAL_THRESHOLD, "dN/dS", "> 1.0"),
    ]

    await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("re-frame after the clarification", "kinases"),
        expected_criteria=3,
    )

    assert declared_sizes == [4]


@pytest.mark.asyncio
async def test_a_declaration_above_the_thread_stands(
    declared_sizes: list[int],
) -> None:
    deps = _deps()
    deps.state.domain.requirements = [
        _requirement(ConstraintKind.ORGANISM, "organism", "Plasmodium falciparum"),
    ]

    await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("operationalize the goal", "kinases"),
        expected_criteria=9,
    )

    assert declared_sizes == [9]
