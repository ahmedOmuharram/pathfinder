from __future__ import annotations

import contextlib

import pytest
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.graph.runtime import AgentDeps


@pytest.mark.asyncio
async def test_discovery_finds_kinase_membrane_searches(
    deps_discovery: AgentDeps,
) -> None:
    """Given a well-formed problem frame for kinase + membrane + EST,
    discovery should register at least one of the four expected searches.

    Asserts only on the side effect (``agent_state.discovered_searches``)
    because the full PhaseOutcome run can easily exceed the default
    request limit on an open-ended discovery prompt.
    """
    expected_any = {
        "GenesByGoTerm",
        "GenesByTransmembraneDomains",
        "GenesWithSignalPeptide",
        "GenesByESTOverlap",
    }
    prompt = (
        "Discover WDK searches and parameters needed to find Plasmodium "
        "kinase genes (GO:0016301) that are membrane-associated (TM or SP) "
        "with EST overlap evidence. Register searches with "
        "`get_search_overview` (ONE call per search; do NOT re-check)."
    )
    with contextlib.suppress(UsageLimitExceeded):
        await discovery_agent.run(
            prompt,
            deps=deps_discovery,
            usage_limits=UsageLimits(
                request_limit=200, tool_calls_limit=200,
            ),
        )

    found = set(deps_discovery.agent_state.discovered_searches.keys())
    assert found & expected_any, (
        f"discovery must register at least one expected search; "
        f"expected any of {sorted(expected_any)}, found {sorted(found)}"
    )
