"""Tests for the planning agent using pydantic-ai FunctionModel.

FunctionModel lets us return deterministic tool calls so we can verify
the agent executes them and mutates deps correctly.
"""

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents.planning import PLANNING_USAGE_LIMITS, planning_agent
from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.domain.strategy.session import StrategySession


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
    )


@pytest.mark.asyncio
async def test_planning_agent_result_is_string() -> None:
    """planning_agent.run should produce a string result."""
    deps = _make_deps()

    result = await planning_agent.run(
        "Build a plan for finding gametocyte genes",
        deps=deps,
        model=TestModel(call_tools=[]),
        usage_limits=UsageLimits(request_limit=2),
    )

    assert isinstance(result.output, str)
    assert len(result.output) > 0


@pytest.mark.asyncio
async def test_planning_agent_has_correct_name() -> None:
    """Verify the agent's name attribute."""
    assert planning_agent.name == "planning"


@pytest.mark.asyncio
async def test_planning_usage_limits_are_configured() -> None:
    """Verify the default usage limits for the planning phase."""
    assert PLANNING_USAGE_LIMITS.request_limit == 15
    assert PLANNING_USAGE_LIMITS.total_tokens_limit == 40_000


@pytest.mark.asyncio
async def test_planning_agent_calls_create_plan() -> None:
    """FunctionModel returns a create_plan tool call; verify the plan lands in state."""
    deps = _make_deps()

    call_count = 0

    def model_function(
        messages: list[object], info: AgentInfo
    ) -> object:
        nonlocal call_count
        call_count += 1

        # On first call, issue the create_plan tool call.
        # On second call (after tool result), return final text.
        if call_count == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_plan",
                        args={
                            "title": "Gametocyte Gene Plan",
                            "description": "Find genes expressed in gametocytes",
                            "rationale": "Use GenesByTaxon to narrow by organism",
                            "steps": [
                                {
                                    "id": "step_1",
                                    "search_name": "GenesByTaxon",
                                    "display_name": "Genes by Taxon",
                                    "record_type": "transcript",
                                    "step_type": "leaf",
                                    "parameters": {
                                        "organism": '["Plasmodium falciparum 3D7"]'
                                    },
                                }
                            ],
                            "connections": [],
                        },
                        tool_call_id="call_1",
                    )
                ]
            )

        return ModelResponse(parts=[TextPart(content="Plan created successfully.")])

    result = await planning_agent.run(
        "Find gametocyte genes",
        deps=deps,
        model=FunctionModel(model_function),
        usage_limits=UsageLimits(request_limit=5),
    )

    # Verify agent completed
    assert isinstance(result.output, str)
    assert "Plan created" in result.output

    # Verify the plan was actually stored in state
    plan = deps.agent_state.active_plan
    assert plan is not None
    assert plan.title == "Gametocyte Gene Plan"
    assert len(plan.steps) == 1
    assert plan.steps[0].search_name == "GenesByTaxon"
