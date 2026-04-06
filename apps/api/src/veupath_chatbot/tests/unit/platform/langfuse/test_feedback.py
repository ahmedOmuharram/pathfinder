"""Tests for Langfuse user feedback recording."""

from unittest.mock import MagicMock, patch

from veupath_chatbot.platform.langfuse.feedback import record_feedback


def test_record_feedback_noop_when_langfuse_disabled() -> None:
    """No-op when get_langfuse() returns None."""
    with patch(
        "veupath_chatbot.platform.langfuse.feedback.get_langfuse",
        return_value=None,
    ):
        record_feedback(
            trace_id="trace-123",
            stream_id="stream-abc",
            value=1,
            comment="Great answer",
        )  # Should not raise


def test_record_feedback_sends_to_langfuse() -> None:
    """Feedback is recorded as a BOOLEAN-typed score."""
    mock_client = MagicMock()
    with patch(
        "veupath_chatbot.platform.langfuse.feedback.get_langfuse",
        return_value=mock_client,
    ):
        record_feedback(
            trace_id="trace-456",
            stream_id="stream-xyz",
            value=1,
            comment="Helpful",
        )

    mock_client.create_score.assert_called_once_with(
        trace_id="trace-456",
        name="user_feedback",
        value=1,
        data_type="BOOLEAN",
        comment="Helpful",
    )


def test_record_feedback_without_comment() -> None:
    """Feedback without a comment passes None."""
    mock_client = MagicMock()
    with patch(
        "veupath_chatbot.platform.langfuse.feedback.get_langfuse",
        return_value=mock_client,
    ):
        record_feedback(
            trace_id="trace-789",
            stream_id="stream-000",
            value=0,
        )

    mock_client.create_score.assert_called_once_with(
        trace_id="trace-789",
        name="user_feedback",
        value=0,
        data_type="BOOLEAN",
        comment=None,
    )


def test_record_feedback_handles_exception() -> None:
    """Exception from Langfuse is caught, not propagated."""
    mock_client = MagicMock()
    mock_client.create_score.side_effect = OSError("Network error")
    with patch(
        "veupath_chatbot.platform.langfuse.feedback.get_langfuse",
        return_value=mock_client,
    ):
        record_feedback(
            trace_id="trace-err",
            stream_id="stream-err",
            value=1,
        )  # Should not raise
