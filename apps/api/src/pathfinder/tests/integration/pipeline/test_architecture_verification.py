"""Architecture verification tests — prove Yi's design works end-to-end.

Tests the architectural components in sequence with real domain objects.
Only the LLM is mocked (via TestModel/FunctionModel). All services,
domain models, and state management are real.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from pydantic_ai import UsageLimits
from pydantic_ai.models.test import TestModel

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import (
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.orchestration.classifier import Intent, classify_request
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.ai.tools.standalone._plan_models import PlannedStepInput
from pathfinder.ai.tools.standalone.plan import create_plan, submit_plan
from pathfinder.domain.strategy.plan import (
    PlannedConnection,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.chat.streaming.step_execution import (
    allowed_tools_for_step,
)


def _make_deps(site_id: str = "plasmodb.org") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _make_ctx(deps: AgentDeps) -> object:
    """Create a mock RunContext wrapping real deps."""

    ctx = MagicMock()
    ctx.deps = deps
    return ctx


class TestArchitectureStage1Classifier:
    """Stage 1: Request classification produces correct intents."""

    def test_new_strategy_classified_correctly(self) -> None:
        result = classify_request("Find malaria genes in P. falciparum")
        assert result is not None
        assert result.intent == Intent.NEW_STRATEGY
        assert result.confidence >= 0.80

    def test_extend_classified_with_graph(self) -> None:

        graph = MagicMock()
        graph.steps = {"step_1": MagicMock()}
        result = classify_request("Also add genes by GO term", graph=graph)
        assert result is not None
        assert result.intent == Intent.EXTEND_STRATEGY

    def test_question_classified_correctly(self) -> None:
        result = classify_request("What does PF3D7_1133400 do?")
        assert result is not None
        assert result.intent == Intent.QUESTION


class TestArchitectureStage2StateMachine:
    """Stage 2: State machine starts in discovery and traverses phases."""

    def test_pipeline_starts_in_discovery(self) -> None:
        pipeline = create_pipeline()
        assert pipeline.current_phase == "discovery"
        assert pipeline.is_done is False

    def test_pipeline_full_traversal(self) -> None:
        pipeline = create_pipeline()

        # Discovery phase
        pipeline.send("analyze")
        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"

        # Planning phase
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        # Execution phase
        pipeline.send("finish_execution")
        assert pipeline.current_phase == "verification"

        # Verification phase
        pipeline.send("finish_verification")
        assert pipeline.is_done is True


class TestArchitectureStage3DiscoveryAgent:
    """Stage 3: Discovery agent runs with TestModel and produces results."""

    @pytest.mark.asyncio
    async def test_discovery_agent_runs(self) -> None:
        deps = _make_deps()
        with discovery_agent.override(model=TestModel(call_tools=[])):
            result = await discovery_agent.run(
                "Find malaria genes",
                deps=deps,
                usage_limits=UsageLimits(request_limit=3),
            )
        assert isinstance(result.output, str)
        assert len(result.output) > 0



class TestArchitectureStage4PlanningAgent:
    """Stage 4: Planning creates a plan, submit_plan pauses for approval."""

    @pytest.mark.asyncio
    async def test_create_and_submit_plan(self) -> None:
        deps = _make_deps()
        ctx = _make_ctx(deps)

        # Create plan with real domain objects
        result = await create_plan(
            ctx,
            title="Malaria gene search",
            description="Find P. falciparum genes",
            rationale="Using taxon-based search",
            steps=[
                PlannedStepInput(
                    search_name="GenesByTaxon",
                    display_name="P. falciparum genes",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                ),
            ],
            connections=[],
        )
        assert not isinstance(result, dict) or "error" not in result

        # Verify plan stored in agent state
        plan = deps.agent_state.active_plan
        assert plan is not None
        assert plan.title == "Malaria gene search"
        assert len(plan.steps) == 1
        assert plan.steps[0].search_name == "GenesByTaxon"

        # Submit plan — should change status to PRESENTED
        submit_result = await submit_plan(ctx)
        assert not isinstance(submit_result, dict) or "error" not in submit_result
        assert deps.agent_state.active_plan.status == PlanStatus.PRESENTED

        # Verify SSE events were emitted
        events = []
        while not deps.event_queue.empty():
            events.append(deps.event_queue.get_nowait())
        event_types = [e["type"] for e in events]
        assert "plan_presented" in event_types



class TestArchitectureStage5PlanGuidedExecution:
    """Stage 5: Plan-guided execution uses FilteredToolset per step."""

    def test_allowed_tools_for_leaf_step(self) -> None:

        step = PlannedStep(
            id="step_1",
            search_name="GenesByTaxon",
            display_name="Test",
            record_type="transcript",
            step_type=StepType.LEAF,
            status=StepStatus.READY,
        )
        tools = allowed_tools_for_step(step)
        assert "create_leaf_step" in tools
        assert "get_strategy" in tools

    def test_allowed_tools_for_combine_step(self) -> None:

        step = PlannedStep(
            id="step_2",
            search_name="__combine__",
            display_name="Combined",
            record_type="transcript",
            step_type=StepType.COMBINE,
            status=StepStatus.READY,
        )
        tools = allowed_tools_for_step(step)
        assert "combine_steps" in tools
        assert "create_leaf_step" not in tools

    def test_execution_usage_limits_are_tight(self) -> None:
        assert EXECUTION_USAGE_LIMITS.request_limit == 3

    @pytest.mark.asyncio
    async def test_execution_agent_runs_with_test_model(self) -> None:
        deps = _make_deps()
        with execution_agent.override(model=TestModel(call_tools=[])):
            result = await execution_agent.run(
                "Execute the plan",
                deps=deps,
                usage_limits=UsageLimits(request_limit=2),
            )
        assert isinstance(result.output, str)


class TestArchitectureStage6VerificationAgent:
    """Stage 6: Verification agent runs and produces results."""

    @pytest.mark.asyncio
    async def test_verification_agent_runs(self) -> None:
        deps = _make_deps()
        with verification_agent.override(model=TestModel(call_tools=[])):
            result = await verification_agent.run(
                "Verify the results",
                deps=deps,
                usage_limits=UsageLimits(request_limit=2),
            )
        assert isinstance(result.output, str)
        assert len(result.output) > 0


class TestArchitectureCrossPhaseContext:
    """Cross-phase message passing: discovery → planning."""

    @pytest.mark.asyncio
    async def test_discovery_messages_passed_to_planning(self) -> None:
        """Discovery agent's messages can be captured for planning."""
        deps = _make_deps()
        with discovery_agent.override(model=TestModel(call_tools=[])):
            result = await discovery_agent.run(
                "Find malaria genes",
                deps=deps,
                usage_limits=UsageLimits(request_limit=2),
            )
        # Capture messages for next phase
        discovery_messages = result.new_messages()
        assert len(discovery_messages) > 0

        # Planning agent can receive these messages
        with planning_agent.override(model=TestModel(call_tools=[])):
            plan_result = await planning_agent.run(
                "Create a plan",
                deps=deps,
                message_history=discovery_messages,
                usage_limits=UsageLimits(request_limit=2),
            )
        assert isinstance(plan_result.output, str)


class TestArchitectureDependencyOrdering:
    """Plan steps execute in dependency order."""

    def test_steps_in_dependency_order(self) -> None:

        plan = StrategyPlan(
            title="Test",
            description="Test plan",
            rationale="Testing",
            steps=[
                PlannedStep(
                    id="leaf_a",
                    search_name="GenesByTaxon",
                    display_name="Step A",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    status=StepStatus.READY,
                ),
                PlannedStep(
                    id="leaf_b",
                    search_name="GenesByGoTerm",
                    display_name="Step B",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    status=StepStatus.READY,
                ),
                PlannedStep(
                    id="combine_c",
                    search_name="__combine__",
                    display_name="Combined",
                    record_type="transcript",
                    step_type=StepType.COMBINE,
                    status=StepStatus.READY,
                ),
            ],
            connections=[
                PlannedConnection(from_step="leaf_a", to_step="combine_c"),
                PlannedConnection(from_step="leaf_b", to_step="combine_c"),
            ],
        )

        ordered = plan.steps_in_dependency_order()
        ordered_ids = [s.id for s in ordered]

        # Leaves must come before combine
        assert ordered_ids.index("leaf_a") < ordered_ids.index("combine_c")
        assert ordered_ids.index("leaf_b") < ordered_ids.index("combine_c")
        # All steps present
        assert len(ordered_ids) == 3
