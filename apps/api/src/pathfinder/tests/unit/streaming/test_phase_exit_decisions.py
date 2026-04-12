"""Unit tests for strict phase-exit decisions in the streaming producer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.orchestration.classifier import Intent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    ClarificationQuestion,
    DiscoveryResult,
    PhaseDecision,
    PlanningResult,
    ProblemFrame,
    ScopingResult,
    VerificationResult,
)
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.ai.tools.standalone._plan_models import PlannedStepInput
from pathfinder.ai.tools.standalone.plan import create_plan, submit_plan
from pathfinder.domain.strategy.plan import PlanStatus, StepType
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.phase_driver import (
    check_plan_approval,
    run_sm_phase,
)
from pathfinder.services.chat.streaming.phase_runner import PhaseConfig
from pathfinder.services.chat.streaming.turn_telemetry import (
    PhaseEventContext,
    PhaseTimingTracker,
)

_PHASE = PipelinePhaseConfig(model_id="mock/deterministic", reasoning_effort="low")
_PIPELINE = PipelineConfig(
    scoping=_PHASE,
    discovery=_PHASE,
    planning=_PHASE,
    execution=_PHASE,
    verification=_PHASE,
)


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    session.create_graph("Decision Test Strategy")
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _make_config(phase: str, deps: AgentDeps) -> PhaseConfig:
    return PhaseConfig(
        phase=phase,
        prompt="",
        deps=deps,
        queue=asyncio.Queue(),
        message_id=f"{phase}-msg",
        counters=TurnCounters(),
        message_group_id="group-1",
        model_id="mock/deterministic",
        reasoning_effort="low",
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _leaf_step(step_id: str = "step_a") -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )


def _phase_message_runner(content: str) -> AsyncMock:
    async def _runner(config: PhaseConfig) -> list[object]:
        config.counters.accumulated_text_parts.append(content)
        config.counters.saw_assistant_message = True
        return []

    return AsyncMock(side_effect=_runner)


@pytest.mark.asyncio
async def test_run_sm_phase_requires_finish_scoping() -> None:
    deps = _make_deps()
    sm = create_pipeline()

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ), pytest.raises(ValueError, match="finish_scoping"):
        await run_sm_phase(
            sm,
            _make_config("scoping", deps),
            None,
            PhaseTimingTracker(),
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
        )


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_continue_decision_from_problem_frame() -> None:
    deps = _make_deps()
    frame = ProblemFrame(
        user_goal="Find membrane transporters",
        interpreted_goal="Identify P. vivax membrane transporters",
        organism_scope="Plasmodium vivax",
        record_type="gene",
        ready_for_wdk_discovery=True,
        confidence=0.9,
    )
    deps.problem_frame = frame
    deps.scoping_result = ScopingResult(problem_frame=frame)
    sm = create_pipeline()
    recoveries: list[tuple[str, str, str, object | None]] = []

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ):
        discovery_messages, should_break = await run_sm_phase(
            sm,
            _make_config("scoping", deps),
            None,
            PhaseTimingTracker(),
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
            record_recovery=lambda phase, kind, summary, metadata: recoveries.append(
                (phase, kind, summary, metadata)
            ),
        )

    assert discovery_messages == []
    assert should_break is False
    assert deps.scoping_result is not None
    assert deps.scoping_result.decision is not None
    assert deps.scoping_result.decision.decision == "continue_to_discovery"
    assert sm.current_phase == "discovery"
    assert recoveries == [
        (
            "scoping",
            "missing_finish_scoping",
            "Recovered missing finish_scoping from saved problem frame.",
            {
                "readyForWdkDiscovery": True,
                "blockingQuestionCount": 0,
                "recoveredDecision": "continue_to_discovery",
            },
        )
    ]


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_ask_user_decision_from_problem_frame() -> None:
    deps = _make_deps()
    frame = ProblemFrame(
        user_goal="Find membrane transporters",
        interpreted_goal="Identify P. vivax membrane transporters",
        organism_scope="Plasmodium vivax",
        record_type="gene",
        ready_for_wdk_discovery=False,
        confidence=0.6,
        blocking_questions=[
            ClarificationQuestion(
                question="How many transmembrane domains should define multiple?",
            )
        ],
    )
    deps.problem_frame = frame
    deps.scoping_result = ScopingResult(problem_frame=frame)
    sm = create_pipeline()
    config = _make_config("scoping", deps)
    phase_timings = PhaseTimingTracker()
    phase_timings.start("scoping")

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ):
        discovery_messages, should_break = await run_sm_phase(
            sm,
            config,
            None,
            phase_timings,
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
        )

    assert discovery_messages == []
    assert should_break is True
    assert deps.scoping_result is not None
    assert deps.scoping_result.decision is not None
    assert deps.scoping_result.decision.decision == "ask_user"

    event = await config.queue.get()
    assert event["type"] == "phase_change"
    data = event["data"]
    assert isinstance(data, dict)
    assert data["phase"] == "scoping"
    assert data["status"] == "awaiting_input"


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_discovery_pause_from_assistant_question() -> None:
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="Find genes by taxon",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )
    sm = create_pipeline()
    sm.send("finish_scoping")
    config = _make_config("discovery", deps)
    phase_timings = PhaseTimingTracker()
    phase_timings.start("discovery")

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=_phase_message_runner(
            "Would you like me to prepare a plan now, or should I narrow the domain choices first?"
        ),
    ):
        _, should_break = await run_sm_phase(
            sm,
            config,
            None,
            phase_timings,
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
        )

    assert should_break is True
    assert deps.discovery_result is not None
    assert deps.discovery_result.decision is not None
    assert deps.discovery_result.decision.decision == "ask_user"

    event = await config.queue.get()
    assert event["type"] == "phase_change"
    data = event["data"]
    assert isinstance(data, dict)
    assert data["phase"] == "discovery"
    assert data["status"] == "awaiting_input"


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_discovery_continue_from_discovered_searches() -> None:
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="Find genes by taxon",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )
    deps.discovery_result = DiscoveryResult(
        discovered_searches=dict(deps.agent_state.discovered_searches),
        intent_summary="Find parasite genes",
    )
    sm = create_pipeline()
    sm.send("finish_scoping")
    recoveries: list[tuple[str, str, str, object | None]] = []

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ):
        _, should_break = await run_sm_phase(
            sm,
            _make_config("discovery", deps),
            None,
            PhaseTimingTracker(),
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
            record_recovery=lambda phase, kind, summary, metadata: recoveries.append(
                (phase, kind, summary, metadata)
            ),
        )

    assert should_break is False
    assert deps.discovery_result is not None
    assert deps.discovery_result.decision is not None
    assert deps.discovery_result.decision.decision == "continue_to_planning"
    assert sm.current_phase == "planning"
    assert recoveries == [
        (
            "discovery",
            "missing_finish_discovery",
            "Recovered missing finish_discovery from discovered catalog context.",
            {
                "discoveredSearchCount": 1,
                "hasResearchNotes": False,
                "hasIntentSummary": True,
                "recoveredDecision": "continue_to_planning",
            },
        )
    ]


@pytest.mark.asyncio
async def test_run_sm_phase_pauses_planning_for_user_input() -> None:
    deps = _make_deps()
    deps.planning_result = PlanningResult(
        decision=PhaseDecision(
            phase="planning",
            decision="ask_user",
            summary="Need a threshold before I can present the plan.",
        )
    )
    sm = create_pipeline()
    sm.send("finish_scoping")
    sm.send("finish_discovery")

    config = _make_config("planning", deps)
    phase_timings = PhaseTimingTracker()
    phase_timings.start("planning")

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ):
        _, should_break = await run_sm_phase(
            sm,
            config,
            None,
            phase_timings,
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
        )

    assert should_break is True

    event = await config.queue.get()
    assert event["type"] == "phase_change"
    data = event["data"]
    assert isinstance(data, dict)
    assert data["phase"] == "planning"
    assert data["status"] == "awaiting_input"
    assert isinstance(data.get("emittedAt"), str)
    assert isinstance(data.get("phaseStartedAt"), str)
    assert isinstance(data.get("phaseCompletedAt"), str)
    assert isinstance(data.get("durationMs"), int)


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_present_plan_from_presented_plan_state() -> None:
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="Find genes by taxon",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )
    ctx = _make_ctx(deps)
    await create_plan(
        ctx,
        title="Recovered planning",
        description="Test recovery from a presented plan",
        rationale="Exercise planning recovery",
        steps=[_leaf_step()],
        connections=[],
    )
    await submit_plan(ctx)
    active_plan = deps.agent_state.active_plan
    assert active_plan is not None

    sm = create_pipeline()
    sm.send("finish_scoping")
    sm.send("finish_discovery")
    recoveries: list[tuple[str, str, str, object | None]] = []

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=AsyncMock(return_value=[]),
    ):
        _, should_break = await run_sm_phase(
            sm,
            _make_config("planning", deps),
            None,
            PhaseTimingTracker(),
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
            record_recovery=lambda phase, kind, summary, metadata: recoveries.append(
                (phase, kind, summary, metadata)
            ),
        )

    assert should_break is True
    assert deps.planning_result is not None
    assert deps.planning_result.decision is not None
    assert deps.planning_result.decision.decision == "present_plan"
    assert recoveries[0] == (
        "planning",
        "missing_finish_planning",
        "Recovered missing finish_planning from presented plan state.",
        {
            "planId": active_plan.id,
            "planStatus": "presented",
            "stepCount": 1,
            "recoveredDecision": "present_plan",
        },
    )


@pytest.mark.asyncio
async def test_run_sm_phase_recovers_verification_completion_from_summary_text() -> None:
    deps = _make_deps()
    deps.verification_result = VerificationResult(sample_record_count=8, enrichment_ran=True)
    sm = create_pipeline()
    sm.send("finish_scoping")
    sm.send("finish_discovery")
    sm.send("submit_draft")
    sm.send("approve")
    sm.send("finish_execution")

    with patch(
        "pathfinder.services.chat.streaming.phase_driver.run_phase",
        new=_phase_message_runner("Verification complete. The final strategy returned 8 genes."),
    ):
        _, should_break = await run_sm_phase(
            sm,
            _make_config("verification", deps),
            None,
            PhaseTimingTracker(),
            PhaseEventContext(
                intent=Intent.NEW_STRATEGY,
                model_id="mock/deterministic",
                run_kind="chat",
            ),
        )

    assert should_break is False
    assert deps.verification_result is not None
    assert deps.verification_result.decision is not None
    assert deps.verification_result.decision.decision == "complete"
    assert deps.verification_result.assessment == (
        "Verification complete. The final strategy returned 8 genes."
    )
    assert sm.current_phase == "completed"


@pytest.mark.asyncio
async def test_check_plan_approval_pauses_even_in_mock_mode() -> None:
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="Find genes by taxon",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Mock Approval Test",
        description="A single-step plan for approval testing",
        rationale="Exercise the approval pause path",
        steps=[_leaf_step()],
        connections=[],
    )
    submit_result = await submit_plan(ctx)

    assert submit_result is not None
    assert deps.agent_state.active_plan is not None
    assert deps.agent_state.active_plan.status == PlanStatus.PRESENTED

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    phase_timings = PhaseTimingTracker()
    phase_timings.start("planning")
    should_pause = await check_plan_approval(
        deps,
        queue,
        phase_timings,
        phase_ctx=PhaseEventContext(
            intent=Intent.NEW_STRATEGY,
            model_id="mock/deterministic",
            run_kind="chat",
        ),
        message_id="planning-msg",
        message_group_id="group-1",
    )

    assert should_pause is True
    assert deps.agent_state.active_plan.status == PlanStatus.PRESENTED

    event = await queue.get()
    assert event["type"] == "phase_change"
    data = event["data"]
    assert isinstance(data, dict)
    assert data["phase"] == "planning"
    assert data["status"] == "awaiting_approval"
    assert isinstance(data.get("emittedAt"), str)
    assert isinstance(data.get("phaseStartedAt"), str)
    assert isinstance(data.get("phaseCompletedAt"), str)
    assert isinstance(data.get("durationMs"), int)
