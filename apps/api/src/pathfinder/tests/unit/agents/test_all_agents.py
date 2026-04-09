"""Cross-agent consistency tests for all four phase agents.

Individual agent behavior is tested in test_execution_agent.py,
test_planning_agent.py, and test_verification_agent.py.  This file
only tests cross-agent invariants.
"""

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.domain.strategy.session import StrategySession


def _make_deps(site_id: str = "plasmodb.org") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


class TestCrossAgentConsistency:
    """Verify consistent patterns across all four agents."""

    def test_all_agents_use_same_model_string(self) -> None:
        """All phase agents point to the same LLM model."""
        expected = "anthropic:claude-sonnet-4-5"
        assert discovery_agent._model == expected
        assert planning_agent._model == expected
        assert execution_agent._model == expected
        assert verification_agent._model == expected

    def test_all_agents_have_unique_names(self) -> None:
        names = [
            discovery_agent.name,
            planning_agent.name,
            execution_agent.name,
            verification_agent.name,
        ]
        assert len(set(names)) == 4
        assert set(names) == {"discovery", "planning", "execution", "verification"}

    def test_all_agents_have_at_least_one_toolset(self) -> None:
        for agent in [discovery_agent, planning_agent, execution_agent, verification_agent]:
            assert len(agent._user_toolsets) >= 1, f"{agent.name} has no toolsets"

    def test_all_agents_accept_agent_deps(self) -> None:
        """All agents are configured with AgentDeps as deps_type."""
        for agent in [discovery_agent, planning_agent, execution_agent, verification_agent]:
            assert agent._deps_type is AgentDeps, f"{agent.name} deps_type is not AgentDeps"

    @pytest.mark.asyncio
    async def test_all_agents_return_string_output(self) -> None:
        """All agents produce str output, not structured models."""
        deps = _make_deps()

        for agent in [discovery_agent, planning_agent, execution_agent, verification_agent]:
            result = await agent.run(
                "Find genes in Plasmodium falciparum related to erythrocyte invasion",
                deps=deps,
                model=TestModel(call_tools=[]),
                usage_limits=UsageLimits(request_limit=2),
            )
            assert type(result.output) is str, (
                f"{agent.name} returned {type(result.output)}, expected str"
            )
