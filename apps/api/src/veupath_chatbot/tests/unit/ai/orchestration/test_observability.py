"""Tests for modular observability setup."""

import logging
from unittest.mock import MagicMock, patch

from veupath_chatbot.ai.orchestration.observability import (
    _configure_log_export,
    get_tracer,
    setup_observability,
)


def test_setup_observability_noop_without_config() -> None:
    """No-ops when neither SigNoz nor Langfuse is configured."""
    mock_settings = MagicMock(signoz_otel_endpoint=None, langfuse_secret_key="")
    with patch(
        "veupath_chatbot.ai.orchestration.observability.get_settings",
        return_value=mock_settings,
    ):
        setup_observability(app=MagicMock(), db_engine=MagicMock())


def test_get_tracer_returns_tracer() -> None:
    tracer = get_tracer()
    assert tracer is not None


def test_configure_log_export_noop_without_signoz() -> None:
    """Log export is not configured when SigNoz is disabled."""
    mock_settings = MagicMock(signoz_otel_endpoint=None)
    root = logging.getLogger()
    handler_count_before = len(root.handlers)
    with patch(
        "veupath_chatbot.ai.orchestration.observability.get_settings",
        return_value=mock_settings,
    ):
        _configure_log_export()
    assert len(root.handlers) == handler_count_before


def test_configure_log_export_attaches_handler_with_signoz() -> None:
    """OTLP log handler is attached to root logger when SigNoz is enabled."""
    mock_settings = MagicMock(signoz_otel_endpoint="http://localhost:4317")
    root = logging.getLogger()
    handler_count_before = len(root.handlers)
    with (
        patch(
            "veupath_chatbot.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "veupath_chatbot.ai.orchestration.observability.GrpcLogExporter",
        ),
        patch(
            "veupath_chatbot.ai.orchestration.observability.BatchLogRecordProcessor",
        ),
    ):
        _configure_log_export()
    assert len(root.handlers) == handler_count_before + 1
    # Clean up: remove the handler we just added
    root.handlers.pop()
