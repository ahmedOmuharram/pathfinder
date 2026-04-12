"""Unit tests for structured phase-exit tools."""

from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    ClarificationQuestion,
    DiscoveryResult,
    ProblemFrame,
)
from pathfinder.ai.tools.standalone._plan_models import PlannedStepInput
from pathfinder.ai.tools.standalone.phase_decision import (
    PhaseDecisionResponse,
    finish_discovery,
    finish_planning,
    finish_scoping,
    finish_verification,
)
from pathfinder.ai.tools.standalone.plan import create_plan, submit_plan
from pathfinder.domain.strategy.plan import PlanStatus, StepType
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )


def _leaf_step(step_id: str = "step_a") -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )


@pytest.mark.asyncio
async def test_finish_scoping_requires_problem_frame() -> None:
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await finish_scoping(
        ctx,
        decision="ask_user",
        summary="Need the organism first.",
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "MISSING_PROBLEM_FRAME"


@pytest.mark.asyncio
async def test_finish_scoping_stores_decision_and_questions() -> None:
    deps = _make_deps()
    deps.problem_frame = ProblemFrame(
        user_goal="Find transporters",
        interpreted_goal="Identify transporter genes",
        organism_scope="P. vivax",
        record_type="transcript",
        ready_for_wdk_discovery=False,
        confidence=0.8,
    )
    ctx = _make_ctx(deps)

    result = await finish_scoping(
        ctx,
        decision="ask_user",
        summary="Need the organism cutoff clarified before discovery.",
        questions=[
            ClarificationQuestion(
                question="Which organism should I use?",
                context="This changes the available WDK datasets.",
            )
        ],
    )

    assert isinstance(result, PhaseDecisionResponse)
    assert deps.scoping_result is not None
    assert deps.scoping_result.decision is not None
    assert deps.scoping_result.decision.decision == "ask_user"
    assert deps.scoping_result.decision.questions[0].question == (
        "Which organism should I use?"
    )


@pytest.mark.asyncio
async def test_finish_discovery_preserves_discovered_searches() -> None:
    deps = _make_deps()
    deps.discovery_result = DiscoveryResult(
        discovered_searches={
            "GenesByTaxon": SearchOverview(
                search_name="GenesByTaxon",
                display_name="Genes by Taxon",
                record_type="transcript",
                description="Find genes by taxon",
                parameter_names=["organism"],
                required_params=["organism"],
            )
        },
        research_notes="Found a usable taxon search.",
        intent_summary="Find parasite genes",
    )
    ctx = _make_ctx(deps)

    result = await finish_discovery(
        ctx,
        decision="continue_to_planning",
        summary="Discovery gathered enough search detail to plan safely.",
    )

    assert isinstance(result, PhaseDecisionResponse)
    assert deps.discovery_result is not None
    assert "GenesByTaxon" in deps.discovery_result.discovered_searches
    assert deps.discovery_result.decision is not None
    assert deps.discovery_result.decision.decision == "continue_to_planning"


@pytest.mark.asyncio
async def test_finish_planning_requires_presented_plan() -> None:
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await finish_planning(
        ctx,
        decision="present_plan",
        summary="Plan is ready.",
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "PLAN_NOT_PRESENTED"


@pytest.mark.asyncio
async def test_finish_planning_accepts_presented_plan() -> None:
    deps = _make_deps()
    _register_search(deps.agent_state, "GenesByTaxon")
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Transporter Plan",
        description="Plan to find transporter genes",
        rationale="Start from organism scope",
        steps=[_leaf_step()],
        connections=[],
    )
    submit_result = await submit_plan(ctx)

    assert not isinstance(submit_result, ToolErrorPayload)
    assert deps.agent_state.active_plan is not None
    assert deps.agent_state.active_plan.status == PlanStatus.PRESENTED

    result = await finish_planning(
        ctx,
        decision="present_plan",
        summary="The plan is in the plan card and ready for user review.",
    )

    assert isinstance(result, PhaseDecisionResponse)
    assert deps.planning_result is not None
    assert deps.planning_result.decision is not None
    assert deps.planning_result.decision.decision == "present_plan"


@pytest.mark.asyncio
async def test_finish_verification_records_completion_summary() -> None:
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await finish_verification(
        ctx,
        decision="complete",
        summary="Verification confirmed a reasonable result set.",
    )

    assert isinstance(result, PhaseDecisionResponse)
    assert deps.verification_result is not None
    assert deps.verification_result.assessment == (
        "Verification confirmed a reasonable result set."
    )
    assert deps.verification_result.decision is not None
    assert deps.verification_result.decision.decision == "complete"
