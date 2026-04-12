"""Unit tests for the AgentPipeline state machine."""

import pytest
from statemachine import State, StateChart

from pathfinder.ai.orchestration.pipeline import (
    AgentPipeline,
    create_pipeline,
)


def _make_pipeline() -> AgentPipeline:
    """Create a fresh pipeline with tracker wired up."""
    return create_pipeline()


def _finish_scoping(pipeline: AgentPipeline) -> None:
    pipeline.send("finish_scoping")


def _advance_to_planning(pipeline: AgentPipeline) -> None:
    pipeline.send("finish_scoping")
    pipeline.send("finish_discovery")


class TestInitialState:
    def test_starts_in_scoping_framing(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.current_phase == "scoping"
        state_ids = {s.id for s in pipeline.configuration}
        assert "scoping" in state_ids
        assert "framing" in state_ids

    def test_not_done_initially(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.is_done is False

    def test_retry_counts_initialized(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.retry_counts == {
            "scoping": 1,
            "discovery": 0,
            "planning": 0,
            "execution": 0,
        }


class TestScopingPhase:
    def test_research_moves_to_researching(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("research")
        state_ids = {s.id for s in pipeline.configuration}
        assert "researching" in state_ids
        assert pipeline.current_phase == "scoping"

    def test_finish_scoping_from_framing(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_scoping")
        assert pipeline.current_phase == "discovery"

    def test_finish_scoping_from_researching(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("research")
        pipeline.send("finish_scoping")
        assert pipeline.current_phase == "discovery"


class TestDiscoveryPhase:
    def test_analyze_moves_to_analyzing(self) -> None:
        pipeline = _make_pipeline()
        _finish_scoping(pipeline)
        pipeline.send("analyze")
        state_ids = {s.id for s in pipeline.configuration}
        assert "analyzing" in state_ids
        assert pipeline.current_phase == "discovery"

    def test_finish_discovery_from_searching(self) -> None:
        pipeline = _make_pipeline()
        _finish_scoping(pipeline)
        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"

    def test_finish_discovery_from_analyzing(self) -> None:
        pipeline = _make_pipeline()
        _finish_scoping(pipeline)
        pipeline.send("analyze")
        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"


class TestPlanningPhase:
    def test_drafting_is_initial_substate(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        state_ids = {s.id for s in pipeline.configuration}
        assert "drafting" in state_ids

    def test_submit_draft_to_awaiting_approval(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        state_ids = {s.id for s in pipeline.configuration}
        assert "awaiting_approval" in state_ids

    def test_approve_transitions_to_execution(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

    def test_revision_cycle(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("request_revision")
        state_ids = {s.id for s in pipeline.configuration}
        assert "revising" in state_ids

        pipeline.send("resubmit")
        state_ids = {s.id for s in pipeline.configuration}
        assert "awaiting_approval" in state_ids

        pipeline.send("approve")
        assert pipeline.current_phase == "execution"


class TestFullPipeline:
    def test_discovery_through_completed(self) -> None:
        pipeline = _make_pipeline()

        pipeline.send("finish_scoping")
        assert pipeline.current_phase == "discovery"

        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"

        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        pipeline.send("finish_execution")
        assert pipeline.current_phase == "verification"

        pipeline.send("finish_verification")
        assert pipeline.current_phase == "completed"
        assert pipeline.is_done is True

    def test_transition_count_tracked(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_scoping")
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("finish_verification")
        assert pipeline._transition_count == 6


class TestErrorRecovery:
    def test_replan_returns_to_planning(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        pipeline.send("replan")
        assert pipeline.current_phase == "planning"
        state_ids = {s.id for s in pipeline.configuration}
        assert "drafting" in state_ids

    def test_replan_increments_planning_retry(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")

        planning_before = pipeline.retry_counts["planning"]
        pipeline.send("replan")
        assert pipeline.retry_counts["planning"] == planning_before + 1

    def test_execution_retry_substates(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")

        pipeline.send("retry")
        state_ids = {s.id for s in pipeline.configuration}
        assert "retrying" in state_ids

        pipeline.send("resume")
        state_ids = {s.id for s in pipeline.configuration}
        assert "running" in state_ids


class TestAbort:
    def test_abort_from_scoping(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("abort_scoping")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_discovery(self) -> None:
        pipeline = _make_pipeline()
        _finish_scoping(pipeline)
        pipeline.send("abort_discovery")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_planning(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("abort_planning")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_execution(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("abort_execution")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_verification(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("abort_verification")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True


class TestRetryBudget:
    def test_replan_blocked_after_budget_exhausted(self) -> None:
        pipeline = _make_pipeline()
        _advance_to_planning(pipeline)
        pipeline.send("submit_draft")
        pipeline.send("approve")

        # Use all 3 retries
        for _ in range(3):
            pipeline.send("replan")
            pipeline.send("submit_draft")
            pipeline.send("approve")

        # 4th replan: guard fails, stays in execution
        pipeline.send("replan")
        assert pipeline.current_phase == "execution"

    def test_should_replan_guard(self) -> None:
        pipeline = _make_pipeline()
        pipeline.retry_counts["execution"] = 0
        assert pipeline.should_replan() is True

        pipeline.retry_counts["execution"] = 3
        assert pipeline.should_replan() is False

    def test_has_retries_left(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.has_retries_left("execution") is True

        pipeline.retry_counts["execution"] = pipeline.retry_budget
        assert pipeline.has_retries_left("execution") is False


class TestPipelineTracker:
    def test_tracker_wired_via_factory(self) -> None:
        pipeline = create_pipeline()
        # Factory creates tracker — verify by checking that
        # entering scoping incremented the count
        assert pipeline.retry_counts["scoping"] == 1

    def test_custom_listener_receives_callbacks(self) -> None:
        entered_phases: list[str] = []

        class TestListener:
            def on_enter_planning(self) -> None:
                entered_phases.append("planning")

            def on_enter_completed(self) -> None:
                entered_phases.append("completed")

        pipeline = create_pipeline(listeners=[TestListener()])
        pipeline.send("finish_scoping")
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("finish_verification")

        assert "planning" in entered_phases
        assert "completed" in entered_phases

    def test_guard_error_propagates(self) -> None:
        """Guard exceptions must propagate, not be silently swallowed.

        Uses a minimal StateChart (not AgentPipeline) because python-statemachine
        resolves guard references at class definition time, making instance
        monkey-patching ineffective.
        """

        class GuardBugChart(StateChart[None]):
            allow_event_without_transition = True
            catch_errors_as_events = False

            s1 = State(initial=True)
            s2 = State(final=True)
            go = s1.to(s2, cond="buggy_guard")

            def buggy_guard(self) -> bool:
                msg = "guard bug"
                raise RuntimeError(msg)

        sm = GuardBugChart()
        with pytest.raises(RuntimeError, match="guard bug"):
            sm.send("go")

    def test_listener_error_propagates(self) -> None:
        """Listener callback exceptions must propagate, not be silently swallowed."""

        class BuggyListener:
            def on_enter_planning(self) -> None:
                msg = "listener bug"
                raise RuntimeError(msg)

        pipeline = create_pipeline(listeners=[BuggyListener()])
        pipeline.send("finish_scoping")
        with pytest.raises(RuntimeError, match="listener bug"):
            pipeline.send("finish_discovery")
