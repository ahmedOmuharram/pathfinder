"""Tests for Langfuse user feedback recording — graceful degradation only."""

from unittest.mock import MagicMock, patch

from pathfinder.platform.langfuse.feedback import record_feedback


def test_record_feedback_noop_when_langfuse_disabled() -> None:
    """No-op when get_langfuse() returns None."""
    with patch(
        "pathfinder.platform.langfuse.feedback.get_langfuse",
        return_value=None,
    ):
        record_feedback(
            trace_id="trace-123",
            stream_id="stream-abc",
            value=1,
            comment="Great answer",
        )  # Should not raise


def test_record_feedback_handles_exception() -> None:
    """Exception from Langfuse is caught, not propagated."""
    mock_client = MagicMock()
    mock_client.create_score.side_effect = OSError("Network error")
    with patch(
        "pathfinder.platform.langfuse.feedback.get_langfuse",
        return_value=mock_client,
    ):
        record_feedback(
            trace_id="trace-err",
            stream_id="stream-err",
            value=1,
        )  # Should not raise
