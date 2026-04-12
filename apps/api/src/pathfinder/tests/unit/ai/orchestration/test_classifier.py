"""Unit tests for request classification helpers."""

from pathfinder.ai.orchestration.classifier import should_resume_paused_phase


def test_should_resume_paused_phase_for_simple_follow_up_answer() -> None:
    assert should_resume_paused_phase("Good") is True
    assert should_resume_paused_phase("Yes, continue with GO term and TM domain") is True


def test_should_not_resume_paused_phase_for_explicit_revision() -> None:
    assert should_resume_paused_phase("Actually use Toxoplasma instead") is False
    assert should_resume_paused_phase("Change the organism to T. gondii") is False
