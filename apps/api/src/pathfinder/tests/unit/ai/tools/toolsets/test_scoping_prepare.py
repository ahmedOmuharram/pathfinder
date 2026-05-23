from __future__ import annotations

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.usage import RunUsage

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import ProblemFrame
from pathfinder.ai.tools.toolsets.scoping import _prepare
from pathfinder.domain.strategy.session import StrategySession

_ALL_SCOPING_TOOLS = [
    ToolDefinition(name="think", description="", parameters_json_schema={}),
    ToolDefinition(name="web_search", description="", parameters_json_schema={}),
    ToolDefinition(
        name="literature_search", description="", parameters_json_schema={},
    ),
    ToolDefinition(
        name="set_problem_frame", description="", parameters_json_schema={},
    ),
]


def _ctx(
    *,
    problem_frame: ProblemFrame | None,
    problem_frame_set_this_run: bool,
    messages: list[ModelRequest | ModelResponse],
) -> RunContext[AgentDeps]:
    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=StrategySession(site_id="plasmodb"),
        problem_frame=problem_frame,
        problem_frame_set_this_run=problem_frame_set_this_run,
    )
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        messages=messages,
    )


def _tool_call_msg(*tool_names: str) -> ModelResponse:
    return ModelResponse(
        parts=[
            ToolCallPart(tool_name=n, args={}, tool_call_id=f"tc-{n}")
            for n in tool_names
        ],
    )


def _user_msg(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


@pytest.mark.anyio
async def test_fresh_run_starts_with_think_only() -> None:
    ctx = _ctx(
        problem_frame=None,
        problem_frame_set_this_run=False,
        messages=[_user_msg("hi")],
    )
    result = await _prepare(ctx, _ALL_SCOPING_TOOLS)
    assert [t.name for t in result] == ["think"]


@pytest.mark.anyio
async def test_after_think_research_unlocks() -> None:
    ctx = _ctx(
        problem_frame=None,
        problem_frame_set_this_run=False,
        messages=[_user_msg("hi"), _tool_call_msg("think")],
    )
    result = await _prepare(ctx, _ALL_SCOPING_TOOLS)
    assert sorted(t.name for t in result) == sorted(
        ["think", "web_search", "literature_search"],
    )


@pytest.mark.anyio
async def test_after_research_set_problem_frame_unlocks() -> None:
    ctx = _ctx(
        problem_frame=None,
        problem_frame_set_this_run=False,
        messages=[
            _user_msg("hi"),
            _tool_call_msg("think"),
            _tool_call_msg("web_search"),
        ],
    )
    result = await _prepare(ctx, _ALL_SCOPING_TOOLS)
    assert sorted(t.name for t in result) == sorted(
        ["think", "web_search", "literature_search", "set_problem_frame"],
    )


@pytest.mark.anyio
async def test_after_set_problem_frame_this_run_tools_vanish() -> None:
    frame = ProblemFrame(
        user_goal="u",
        interpreted_goal="i",
        ready_for_wdk_discovery=True,
    )
    ctx = _ctx(
        problem_frame=frame,
        problem_frame_set_this_run=True,
        messages=[
            _user_msg("hi"),
            _tool_call_msg("think"),
            _tool_call_msg("set_problem_frame"),
        ],
    )
    result = await _prepare(ctx, _ALL_SCOPING_TOOLS)
    assert result == []


@pytest.mark.anyio
async def test_reentry_with_prior_frame_still_exposes_full_toolset() -> None:
    """Regression: turn 2+ enters scoping with ``state.problem_frame`` set.

    The old guard zero'd the toolset in that case, so the agent had no
    way to re-frame. The fix keys on ``problem_frame_set_this_run`` instead,
    which resets per sub-agent run.
    """
    prior_frame = ProblemFrame(
        user_goal="u",
        interpreted_goal="i",
        ready_for_wdk_discovery=True,
    )
    ctx = _ctx(
        problem_frame=prior_frame,
        problem_frame_set_this_run=False,
        messages=[
            _user_msg("first turn"),
            _tool_call_msg("think"),
            _tool_call_msg("web_search"),
            _tool_call_msg("set_problem_frame"),
            _user_msg("reconsider"),
        ],
    )
    result = await _prepare(ctx, _ALL_SCOPING_TOOLS)
    assert "set_problem_frame" in {t.name for t in result}
    assert "think" in {t.name for t in result}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
