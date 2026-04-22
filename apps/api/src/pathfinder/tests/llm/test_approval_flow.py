from __future__ import annotations

import pytest
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)

from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PhaseDisposition, PhaseOutcome

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
    "Call create_plan ONCE with all steps+connections, then submit_plan. "
    "Do NOT re-look-up the search metadata."
)


async def _run_until_approval(
    deps: AgentDeps,
) -> tuple[DeferredToolRequests, list, ToolCallPart]:
    result = await planning_agent.run(_USER_PROMPT, deps=deps)
    output = result.output
    assert isinstance(output, DeferredToolRequests), (
        f"expected DeferredToolRequests; got {type(output).__name__}"
    )
    submit_call = next(
        (c for c in output.approvals if c.tool_name == "submit_plan"), None,
    )
    assert submit_call is not None, "submit_plan must be in approvals queue"
    return output, list(result.new_messages()), submit_call


@pytest.mark.asyncio
async def test_approval_resumes_and_hands_off_to_execution(
    deps_planning: AgentDeps,
) -> None:
    _, history, submit_call = await _run_until_approval(deps_planning)

    resumed = await planning_agent.run(
        deps=deps_planning,
        message_history=history,
        deferred_tool_results=DeferredToolResults(
            approvals={submit_call.tool_call_id: True},
        ),
    )
    output = resumed.output
    assert isinstance(output, PhaseOutcome), (
        f"post-approval run must return PhaseOutcome; got {type(output).__name__}"
    )
    assert output.disposition == PhaseDisposition.HANDOFF, (
        f"expected HANDOFF after approval; got {output.disposition.value} — prose: {output.prose!r}"
    )
    assert output.handoff_to == "execution", (
        f"expected handoff_to=execution; got {output.handoff_to!r}"
    )
    plan = deps_planning.agent_state.active_plan
    assert plan is not None
    assert plan.status.value == "approved", (
        f"plan.status must be APPROVED after approval; got {plan.status.value}"
    )


@pytest.mark.asyncio
async def test_denial_keeps_plan_unapproved_and_invites_changes(
    deps_planning: AgentDeps,
) -> None:
    _, history, submit_call = await _run_until_approval(deps_planning)

    resumed = await planning_agent.run(
        deps=deps_planning,
        message_history=history,
        deferred_tool_results=DeferredToolResults(
            approvals={
                submit_call.tool_call_id: ToolDenied(
                    message=(
                        "User did not approve. Message: also include "
                        "Plasmodium vivax explicitly in the organism scope "
                        "and require GO evidence code 'Curated' only."
                    ),
                ),
            },
        ),
    )
    plan = deps_planning.agent_state.active_plan
    assert plan is not None
    assert plan.status.value != "approved", (
        f"denial must not approve the plan; got {plan.status.value}"
    )
    output = resumed.output
    assert isinstance(output, (PhaseOutcome, DeferredToolRequests)), (
        f"post-denial run must return PhaseOutcome or DeferredToolRequests; "
        f"got {type(output).__name__}"
    )
