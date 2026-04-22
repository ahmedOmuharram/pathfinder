from __future__ import annotations

import pytest
from pydantic_ai.tools import DeferredToolRequests

from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.graph.runtime import AgentDeps

_USER_PROMPT = (
    "Build a plan using these exact WDK searches (already discovered):\n"
    "- GenesByGoTerm (kinase activity GO:0016301, curated+computed, "
    "organism=Plasmodium)\n"
    "- GenesByTransmembraneDomains (Plasmodium, min_tm=1)\n"
    "- GenesWithSignalPeptide (Plasmodium)\n"
    "- GenesByESTOverlap (libraryIdGenes=Plasmodium, bp_overlap_gte=100, "
    "min_percent_identity=90)\n\n"
    "Topology: leaf(kinase), leaf(tm), leaf(sp), union(tm,sp), "
    "intersect(kinase, union), leaf(est), intersect(previous, est). "
    "Call create_plan ONCE with all these steps+connections, then "
    "submit_plan. Do NOT re-look-up the search metadata — these searches "
    "are ready."
)


@pytest.mark.asyncio
async def test_submit_plan_defers_for_approval(
    deps_planning: AgentDeps,
) -> None:
    """Planner calls submit_plan; pydantic-ai exits with DeferredToolRequests.

    Phase 1's core contract: ``submit_plan`` is registered with
    ``requires_approval=True``, so the agent exits with
    ``DeferredToolRequests(approvals=[...])`` instead of running the tool
    body immediately.
    """
    result = await planning_agent.run(_USER_PROMPT, deps=deps_planning)
    output = result.output
    assert isinstance(output, DeferredToolRequests), (
        f"expected DeferredToolRequests, got {type(output).__name__}: {output!r}"
    )
    assert output.approvals, "submit_plan must be in the approvals queue"
    tool_names = [call.tool_name for call in output.approvals]
    assert "submit_plan" in tool_names, (
        f"submit_plan must defer for approval; got {tool_names}"
    )
    assert deps_planning.agent_state.active_plan is not None, (
        "create_plan should have populated active_plan before submit_plan deferred"
    )
    plan = deps_planning.agent_state.active_plan
    assert plan.status.value == "draft", (
        f"plan.status must still be DRAFT pre-approval; got {plan.status.value}"
    )
