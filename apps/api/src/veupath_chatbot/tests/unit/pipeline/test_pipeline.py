"""Unit tests for the AgentPipeline state machine."""


from veupath_chatbot.ai.orchestration.pipeline import (
    AgentPipeline,
    create_pipeline,
)


def _make_pipeline() -> AgentPipeline:
    """Create a fresh pipeline with tracker wired up."""
    return create_pipeline()


class TestInitialState:
    def test_starts_in_discovery_searching(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.current_phase == "discovery"
        state_ids = {s.id for s in pipeline.configuration}
        assert "discovery" in state_ids
        assert "searching" in state_ids

    def test_not_done_initially(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.is_done is False

    def test_retry_counts_initialized(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.retry_counts == {
            "discovery": 1,
            "planning": 0,
            "execution": 0,
        }


class TestDiscoveryPhase:
    def test_analyze_moves_to_analyzing(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("analyze")
        state_ids = {s.id for s in pipeline.configuration}
        assert "analyzing" in state_ids
        assert pipeline.current_phase == "discovery"

    def test_finish_discovery_from_searching(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"

    def test_finish_discovery_from_analyzing(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("analyze")
        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"


class TestPlanningPhase:
    def test_drafting_is_initial_substate(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        state_ids = {s.id for s in pipeline.configuration}
        assert "drafting" in state_ids

    def test_submit_draft_to_awaiting_approval(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        state_ids = {s.id for s in pipeline.configuration}
        assert "awaiting_approval" in state_ids

    def test_approve_transitions_to_execution(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

    def test_revision_cycle(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
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
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("finish_verification")
        assert pipeline._transition_count == 5


class TestErrorRecovery:
    def test_replan_returns_to_planning(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        pipeline.send("replan")
        assert pipeline.current_phase == "planning"
        state_ids = {s.id for s in pipeline.configuration}
        assert "drafting" in state_ids

    def test_replan_increments_planning_retry(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")

        planning_before = pipeline.retry_counts["planning"]
        pipeline.send("replan")
        assert pipeline.retry_counts["planning"] == planning_before + 1

    def test_execution_retry_substates(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")

        pipeline.send("retry")
        state_ids = {s.id for s in pipeline.configuration}
        assert "retrying" in state_ids

        pipeline.send("resume")
        state_ids = {s.id for s in pipeline.configuration}
        assert "running" in state_ids


class TestAbort:
    def test_abort_from_discovery(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("abort_discovery")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_planning(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("abort_planning")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_execution(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("abort_execution")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

    def test_abort_from_verification(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("abort_verification")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True


class TestRetryBudget:
    def test_replan_blocked_after_budget_exhausted(self) -> None:
        pipeline = _make_pipeline()
        pipeline.send("finish_discovery")
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
        # entering discovery incremented the count
        assert pipeline.retry_counts["discovery"] == 1

    def test_custom_listener_receives_callbacks(self) -> None:
        entered_phases: list[str] = []

        class TestListener:
            def on_enter_planning(self) -> None:
                entered_phases.append("planning")

            def on_enter_completed(self) -> None:
                entered_phases.append("completed")

        pipeline = create_pipeline(listeners=[TestListener()])
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("finish_execution")
        pipeline.send("finish_verification")

        assert "planning" in entered_phases
        assert "completed" in entered_phases
