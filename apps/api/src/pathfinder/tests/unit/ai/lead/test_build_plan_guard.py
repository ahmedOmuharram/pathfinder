from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.sub_agent_dispatch import build_plan
from pathfinder.ai.lead.sub_agent_tools import LeadDeps


def _state(
    *, selected: tuple[str, ...] = (), candidate: tuple[str, ...] = ()
) -> PipelineState:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="find Plasmodium kinases",
    )
    for name in selected + candidate:
        state.discovered_searches[name] = SearchOverview(
            search_name=name,
            display_name=name,
            record_type="transcript",
            description="x",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected" if name in selected else "candidate",
        )
    return state


def _ctx(state: PipelineState) -> MagicMock:
    deps = LeadDeps(
        state=state,
        intent=None,
        runtime=MagicMock(),
        retrieved_memories=[],
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


@pytest.mark.asyncio
async def test_build_plan_refuses_when_no_searches_discovered() -> None:
    """The Lead must not dispatch planning before discovery commits searches —
    otherwise planning has an empty universe and invents search names."""
    ctx = _ctx(_state())

    with pytest.raises(ModelRetry) as excinfo:
        await build_plan(ctx, reason="build the OBP plan")

    assert "discover" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_build_plan_refuses_when_only_unselected_candidates() -> None:
    """Inspected-but-unselected searches are not a committed universe — the
    guard still blocks until discovery selects at least one."""
    ctx = _ctx(_state(candidate=("GenesByText",)))

    with pytest.raises(ModelRetry) as excinfo:
        await build_plan(ctx, reason="build it")

    assert "discover" in str(excinfo.value).lower()
