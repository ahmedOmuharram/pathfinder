from __future__ import annotations

import pytest
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PhaseDisposition, PhaseOutcome

_LIMITS = UsageLimits(request_limit=120, tool_calls_limit=120)


@pytest.mark.asyncio
async def test_ambiguous_prompt_halts_for_user(
    deps_scoping: AgentDeps,
) -> None:
    """A vague prompt must not force discovery — scoping asks questions."""
    prompt = "find kinase genes"
    result = await scoping_agent.run(
        prompt, deps=deps_scoping, usage_limits=_LIMITS,
    )
    output = result.output
    assert isinstance(output, PhaseOutcome)
    assert output.disposition == PhaseDisposition.AWAITING_USER, (
        f"ambiguous scoping should end AWAITING_USER; "
        f"got {output.disposition.value}. prose={output.prose!r}"
    )
    frame = deps_scoping.problem_frame
    if frame is not None:
        assert frame.ready_for_wdk_discovery is False, (
            "ambiguous scoping must not flag ready_for_wdk_discovery; "
            f"frame={frame!r}"
        )


@pytest.mark.asyncio
async def test_specific_prompt_is_ready_for_discovery(
    deps_scoping: AgentDeps,
) -> None:
    """A precise prompt with explicit organism + filters shouldn't block
    discovery with more questions."""
    prompt = (
        "Find all Plasmodium falciparum 3D7 protein-coding genes that have "
        "a predicted signal peptide. No other filters. Call `think` once, "
        "then ONE literature_search, then `set_problem_frame` with "
        "ready_for_wdk_discovery=True."
    )
    result = await scoping_agent.run(
        prompt, deps=deps_scoping, usage_limits=_LIMITS,
    )
    output = result.output
    assert isinstance(output, PhaseOutcome)
    frame = deps_scoping.problem_frame
    assert frame is not None
    assert frame.ready_for_wdk_discovery is True, (
        f"precise prompt should flag ready_for_wdk_discovery=True; "
        f"frame.blocking_questions={frame.blocking_questions!r}"
    )
