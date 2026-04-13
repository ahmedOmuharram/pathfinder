"""Unit tests for ConversationState domain model."""

from pathfinder.domain.strategy.conversation_state import ConversationState


class TestConversationState:
    def test_defaults_to_empty(self) -> None:
        state = ConversationState()
        assert state.current_phase is None
        assert state.phase_status is None
        assert state.intent is None
        assert state.phases_completed == []
        assert state.plan_id is None
        assert state.plan_status is None
        assert state.last_operation_id is None

    def test_round_trips_through_json(self) -> None:
        state = ConversationState(
            current_phase="planning",
            phase_status="awaiting_approval",
            intent="new_strategy",
            phases_completed=["scoping", "discovery"],
            plan_id="plan_7b1dad274763",
            plan_status="presented",
            last_operation_id="op_abc123",
        )
        dumped = state.model_dump(by_alias=True, mode="json")
        restored = ConversationState.model_validate(dumped)
        assert restored == state

    def test_camel_case_aliases(self) -> None:
        state = ConversationState(
            current_phase="scoping",
            phase_status="started",
            phases_completed=["scoping"],
            last_operation_id="op_1",
        )
        dumped = state.model_dump(by_alias=True)
        assert "currentPhase" in dumped
        assert "phaseStatus" in dumped
        assert "phasesCompleted" in dumped
        assert "lastOperationId" in dumped

    def test_parses_from_empty_dict(self) -> None:
        state = ConversationState.model_validate({})
        assert state.current_phase is None

    def test_extra_fields_ignored(self) -> None:
        state = ConversationState.model_validate({"unknownField": "value"})
        assert state.current_phase is None

    def test_record_phase_transition_to_started(self) -> None:
        state = ConversationState()
        updated = state.with_phase_change("scoping", "started", operation_id="op_1")
        assert updated.current_phase == "scoping"
        assert updated.phase_status == "started"
        assert updated.last_operation_id == "op_1"
        assert updated.phases_completed == []

    def test_record_phase_transition_to_completed_tracks_phase(self) -> None:
        state = ConversationState(
            current_phase="scoping",
            phase_status="started",
        )
        updated = state.with_phase_change("scoping", "completed")
        assert updated.phase_status == "completed"
        assert "scoping" in updated.phases_completed

    def test_record_plan_presented(self) -> None:
        state = ConversationState(current_phase="planning")
        updated = state.with_plan_event("plan_presented", plan_id="plan_abc123")
        assert updated.plan_id == "plan_abc123"
        assert updated.plan_status == "presented"

    def test_record_plan_approved(self) -> None:
        state = ConversationState(
            current_phase="planning",
            plan_id="plan_abc123",
            plan_status="presented",
        )
        updated = state.with_plan_event("plan_approved", plan_id="plan_abc123")
        assert updated.plan_status == "approved"

    def test_completed_phases_not_duplicated(self) -> None:
        state = ConversationState(phases_completed=["scoping"])
        updated = state.with_phase_change("scoping", "completed")
        assert updated.phases_completed == ["scoping"]
