"""Tests for conversation_state-based resume phase resolution."""

from pathfinder.domain.strategy.conversation_state import ConversationState
from pathfinder.services.chat.deps import resolve_resume_phase


class TestResolveResumePhase:
    def test_returns_phase_when_awaiting_input(self) -> None:
        state = ConversationState(current_phase="discovery", phase_status="awaiting_input")
        assert resolve_resume_phase(state) == "discovery"

    def test_returns_phase_when_awaiting_approval(self) -> None:
        state = ConversationState(current_phase="planning", phase_status="awaiting_approval")
        assert resolve_resume_phase(state) == "planning"

    def test_returns_none_when_phase_started(self) -> None:
        state = ConversationState(current_phase="scoping", phase_status="started")
        assert resolve_resume_phase(state) is None

    def test_returns_none_when_phase_completed(self) -> None:
        state = ConversationState(current_phase="verification", phase_status="completed")
        assert resolve_resume_phase(state) is None

    def test_returns_none_when_empty(self) -> None:
        state = ConversationState()
        assert resolve_resume_phase(state) is None

    def test_returns_none_for_execution_phase(self) -> None:
        state = ConversationState(current_phase="execution", phase_status="awaiting_input")
        assert resolve_resume_phase(state) is None

    def test_returns_none_for_completed_terminal(self) -> None:
        state = ConversationState(current_phase="completed", phase_status="completed")
        assert resolve_resume_phase(state) is None
