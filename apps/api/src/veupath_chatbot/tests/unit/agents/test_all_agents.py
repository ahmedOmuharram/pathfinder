"""Comprehensive tests for all four phase agents using pydantic-ai TestModel.

Covers discovery, planning, execution, and verification agents:
- Correct name
- Runs with TestModel and returns a string
- Correct tool count
- defer_model_check=True (model stored as string, not resolved)
- Agent-specific behaviors (dynamic instructions, usage limits)
"""

from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents.discovery import (
    DISCOVERY_USAGE_LIMITS,
    discovery_agent,
)
from veupath_chatbot.ai.agents.execution import (
    EXECUTION_RECOVERY_LIMITS,
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from veupath_chatbot.ai.agents.planning import (
    PLANNING_USAGE_LIMITS,
    planning_agent,
)
from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.agents.verification import (
    VERIFICATION_USAGE_LIMITS,
    verification_agent,
)
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb.org") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


def _get_tool_count(agent: Agent[Any, Any]) -> int:
    """Extract the tool count from the agent's first user toolset.

    All phase agents use a single FunctionToolset as their first toolset.
    """
    toolset = agent._user_toolsets[0]
    assert isinstance(toolset, FunctionToolset)
    return len(toolset.tools)


# ===========================================================================
# Discovery agent
# ===========================================================================


class TestDiscoveryAgent:
    """Tests for the discovery-phase agent."""

    def test_discovery_agent_name(self) -> None:
        assert discovery_agent.name == "discovery"

    @pytest.mark.anyio
    async def test_discovery_agent_runs_with_test_model(self) -> None:
        deps = _make_deps()

        result = await discovery_agent.run(
            "Find genes expressed in gametocytes",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=3),
        )

        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_discovery_agent_has_correct_tool_count(self) -> None:
        """Discovery phase has 14 tools."""
        assert _get_tool_count(discovery_agent) == 14

    def test_discovery_agent_defers_model_check(self) -> None:
        """defer_model_check=True means the model is stored as a raw string."""
        assert isinstance(discovery_agent._model, str)
        assert discovery_agent._model == "anthropic:claude-sonnet-4-5"

    def test_discovery_usage_limits(self) -> None:
        assert DISCOVERY_USAGE_LIMITS.request_limit == 20
        assert DISCOVERY_USAGE_LIMITS.total_tokens_limit == 50_000

    @pytest.mark.anyio
    async def test_discovery_agent_dynamic_instructions_include_graph_state(
        self,
    ) -> None:
        """When the graph has steps, pinned_graph_state instruction returns them."""
        deps = _make_deps()

        # Add a step to the graph so pinned_graph_state returns content
        graph = StrategyGraph(
            graph_id="g1", name="Test Strategy", site_id="plasmodb.org",
        )
        step = PlanStepNode(
            search_name="GenesByTaxon",
            display_name="P. falciparum genes",
            parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        graph.add_step(step)
        graph.step_counts[step.id] = 5678
        deps.strategy_session.add_graph(graph)

        result = await discovery_agent.run(
            "What searches are available?",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=2),
        )

        # The agent should run without error even with graph state in instructions
        assert isinstance(result.output, str)

    @pytest.mark.anyio
    async def test_discovery_agent_no_graph_state_when_empty(self) -> None:
        """When no graph exists, pinned_graph_state returns None (no crash)."""
        deps = _make_deps()
        # No graphs added — strategy_session.get_graph(None) returns None

        result = await discovery_agent.run(
            "What record types are available?",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=2),
        )

        assert isinstance(result.output, str)


# ===========================================================================
# Planning agent
# ===========================================================================


class TestPlanningAgent:
    """Tests for the planning-phase agent."""

    def test_planning_agent_name(self) -> None:
        assert planning_agent.name == "planning"

    @pytest.mark.anyio
    async def test_planning_agent_runs_with_test_model(self) -> None:
        deps = _make_deps()

        result = await planning_agent.run(
            "Build a plan for finding gametocyte genes",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=3),
        )

        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_planning_agent_has_correct_tool_count(self) -> None:
        """Planning phase has 8 tools."""
        assert _get_tool_count(planning_agent) == 8

    def test_planning_agent_defers_model_check(self) -> None:
        assert isinstance(planning_agent._model, str)
        assert planning_agent._model == "anthropic:claude-sonnet-4-5"

    def test_planning_usage_limits(self) -> None:
        assert PLANNING_USAGE_LIMITS.request_limit == 15
        assert PLANNING_USAGE_LIMITS.total_tokens_limit == 40_000


# ===========================================================================
# Execution agent
# ===========================================================================


class TestExecutionAgent:
    """Tests for the execution-phase agent."""

    def test_execution_agent_name(self) -> None:
        assert execution_agent.name == "execution"

    @pytest.mark.anyio
    async def test_execution_agent_runs_with_test_model(self) -> None:
        deps = _make_deps()

        result = await execution_agent.run(
            "Execute step 1: create leaf step GenesByTaxon",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=3),
        )

        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_execution_agent_has_correct_tool_count(self) -> None:
        """Execution phase has 12 tools."""
        assert _get_tool_count(execution_agent) == 12

    def test_execution_agent_defers_model_check(self) -> None:
        assert isinstance(execution_agent._model, str)
        assert execution_agent._model == "anthropic:claude-sonnet-4-5"

    def test_execution_usage_limits(self) -> None:
        assert EXECUTION_USAGE_LIMITS.request_limit == 3
        assert EXECUTION_USAGE_LIMITS.total_tokens_limit == 30_000

    def test_execution_recovery_limits(self) -> None:
        """Recovery limits are higher than standard execution limits."""
        assert EXECUTION_RECOVERY_LIMITS.request_limit == 5
        assert EXECUTION_RECOVERY_LIMITS.total_tokens_limit == 50_000
        # Recovery limits strictly higher — narrowing to int for comparison
        recovery_req = EXECUTION_RECOVERY_LIMITS.request_limit
        standard_req = EXECUTION_USAGE_LIMITS.request_limit
        assert recovery_req is not None
        assert standard_req is not None
        assert recovery_req > standard_req

        recovery_tok = EXECUTION_RECOVERY_LIMITS.total_tokens_limit
        standard_tok = EXECUTION_USAGE_LIMITS.total_tokens_limit
        assert recovery_tok is not None
        assert standard_tok is not None
        assert recovery_tok > standard_tok


# ===========================================================================
# Verification agent
# ===========================================================================


class TestVerificationAgent:
    """Tests for the verification-phase agent."""

    def test_verification_agent_name(self) -> None:
        assert verification_agent.name == "verification"

    @pytest.mark.anyio
    async def test_verification_agent_runs_with_test_model(self) -> None:
        deps = _make_deps()

        result = await verification_agent.run(
            "Verify strategy results and run enrichment",
            deps=deps,
            model=TestModel(call_tools=[]),
            usage_limits=UsageLimits(request_limit=3),
        )

        assert isinstance(result.output, str)
        assert len(result.output) > 0

    def test_verification_agent_has_correct_tool_count(self) -> None:
        """Verification phase has 18 tools."""
        assert _get_tool_count(verification_agent) == 18

    def test_verification_agent_defers_model_check(self) -> None:
        assert isinstance(verification_agent._model, str)
        assert verification_agent._model == "anthropic:claude-sonnet-4-5"

    def test_verification_usage_limits(self) -> None:
        assert VERIFICATION_USAGE_LIMITS.request_limit == 15
        assert VERIFICATION_USAGE_LIMITS.total_tokens_limit == 40_000


# ===========================================================================
# Cross-agent consistency
# ===========================================================================


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

    @pytest.mark.anyio
    async def test_all_agents_return_string_output(self) -> None:
        """All agents produce str output, not structured models."""
        deps = _make_deps()

        for agent in [discovery_agent, planning_agent, execution_agent, verification_agent]:
            result = await agent.run(
                "test prompt",
                deps=deps,
                model=TestModel(call_tools=[]),
                usage_limits=UsageLimits(request_limit=2),
            )
            assert type(result.output) is str, (
                f"{agent.name} returned {type(result.output)}, expected str"
            )
