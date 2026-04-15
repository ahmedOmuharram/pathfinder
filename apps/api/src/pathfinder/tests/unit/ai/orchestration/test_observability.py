"""Tests for modular observability setup."""

import logging
from unittest.mock import MagicMock, patch

import pathfinder.ai.orchestration.observability as obs
from pathfinder.ai.orchestration.observability import (
    _build_resource,
    _configure_exporters,
    _configure_log_export,
    setup_observability,
    shutdown_observability,
)


def test_setup_observability_noop_without_config() -> None:
    """No-ops when neither SigNoz nor Langfuse is configured."""
    mock_settings = MagicMock(
        signoz_otel_endpoint=None,
        signoz_trace_otel_http_endpoint=None,
        langfuse_secret_key="",
    )
    with patch(
        "pathfinder.ai.orchestration.observability.get_settings",
        return_value=mock_settings,
    ):
        setup_observability(app=MagicMock(), db_engine=MagicMock())


def test_configure_log_export_noop_without_signoz() -> None:
    """Log export is not configured when SigNoz is disabled."""
    mock_settings = MagicMock(signoz_otel_endpoint=None)
    root = logging.getLogger()
    handler_count_before = len(root.handlers)
    with patch(
        "pathfinder.ai.orchestration.observability.get_settings",
        return_value=mock_settings,
    ):
        _configure_log_export()
    assert len(root.handlers) == handler_count_before


def test_shutdown_observability_flushes_stored_provider() -> None:
    """shutdown_observability calls shutdown on the stored provider reference."""
    mock_provider = MagicMock()
    original = obs._otel.provider
    obs._otel.provider = mock_provider
    try:
        shutdown_observability()
        mock_provider.shutdown.assert_called_once()
    finally:
        obs._otel.provider = original


def test_shutdown_observability_noop_when_no_provider() -> None:
    """shutdown_observability no-ops when no provider was configured."""
    original = obs._otel.provider
    obs._otel.provider = None
    try:
        shutdown_observability()  # Should not raise
    finally:
        obs._otel.provider = original


def test_configure_log_export_attaches_handler_with_signoz() -> None:
    """OTLP log handler is attached to root logger when SigNoz is enabled."""
    mock_settings = MagicMock(signoz_otel_endpoint="http://localhost:4317")
    root = logging.getLogger()
    handler_count_before = len(root.handlers)
    with (
        patch(
            "pathfinder.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "pathfinder.ai.orchestration.observability.GrpcLogExporter",
        ),
        patch(
            "pathfinder.ai.orchestration.observability.BatchLogRecordProcessor",
        ),
    ):
        _configure_log_export()
    assert len(root.handlers) == handler_count_before + 1
    # Clean up: remove the handler we just added
    root.handlers.pop()


def test_shutdown_observability_flushes_meter_provider() -> None:
    """shutdown_observability calls shutdown on the stored meter provider."""
    mock_meter = MagicMock()
    original = obs._otel.meter_provider
    obs._otel.meter_provider = mock_meter
    try:
        shutdown_observability()
        mock_meter.shutdown.assert_called_once()
    finally:
        obs._otel.meter_provider = original


def test_resource_includes_enriched_attributes() -> None:
    """Resource includes service.version and deployment.environment.name."""
    mock_settings = MagicMock(api_env="production")
    with patch(
        "pathfinder.ai.orchestration.observability.get_settings",
        return_value=mock_settings,
    ):
        resource = _build_resource()
    attrs = dict(resource.attributes)
    assert attrs["service.name"] == "pathfinder-api"
    assert "service.version" in attrs
    assert attrs["deployment.environment.name"] == "production"
    assert "service.instance.id" in attrs


def test_configure_exporters_returns_provider_for_langfuse_only() -> None:
    """Langfuse-only setup gets a TracerProvider; SDK attaches its own processor."""
    mock_settings = MagicMock(
        signoz_otel_endpoint=None,
        signoz_trace_otel_http_endpoint=None,
        langfuse_host="http://langfuse:3000",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        api_env="development",
    )

    with (
        patch(
            "pathfinder.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "pathfinder.ai.orchestration.observability.HttpSpanExporter",
        ) as exporter_cls,
    ):
        provider = _configure_exporters()

    assert provider is not None
    exporter_cls.assert_not_called()


def test_setup_observability_triggers_langfuse_sdk_when_key_set() -> None:
    """When Langfuse is configured, setup_observability initializes the SDK.

    The SDK's own ``LangfuseSpanProcessor`` attaches to our TracerProvider and
    owns the actual OTLP export to Langfuse — no manual HttpSpanExporter.
    """
    mock_settings = MagicMock(
        signoz_otel_endpoint=None,
        signoz_trace_otel_http_endpoint=None,
        langfuse_host="http://langfuse:3000",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        api_env="development",
    )

    with (
        patch(
            "pathfinder.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "pathfinder.ai.orchestration.observability.get_langfuse",
        ) as get_langfuse_mock,
        patch(
            "pathfinder.ai.orchestration.observability.trace.set_tracer_provider",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_fastapi",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_database",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_http_clients",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_agents",
        ),
    ):
        setup_observability(app=MagicMock(), db_engine=MagicMock())

    get_langfuse_mock.assert_called_once()


def test_setup_observability_skips_langfuse_sdk_when_key_absent() -> None:
    """Langfuse SDK init is skipped when no secret key is set (SigNoz only)."""
    mock_settings = MagicMock(
        signoz_otel_endpoint=None,
        signoz_trace_otel_http_endpoint="http://signoz:4318/v1/traces",
        langfuse_host="",
        langfuse_public_key="",
        langfuse_secret_key="",
        api_env="development",
    )

    with (
        patch(
            "pathfinder.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "pathfinder.ai.orchestration.observability.get_langfuse",
        ) as get_langfuse_mock,
        patch(
            "pathfinder.ai.orchestration.observability.trace.set_tracer_provider",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_fastapi",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_database",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_http_clients",
        ),
        patch(
            "pathfinder.ai.orchestration.observability._instrument_agents",
        ),
    ):
        setup_observability(app=MagicMock(), db_engine=MagicMock())

    get_langfuse_mock.assert_not_called()


def test_configure_exporters_prefers_signoz_http_for_traces_when_configured() -> None:
    """SigNoz traces can use a dedicated OTLP/HTTP endpoint."""
    mock_settings = MagicMock(
        signoz_otel_endpoint="http://localhost:4317",
        signoz_trace_otel_http_endpoint="http://localhost:4318/v1/traces",
        langfuse_host="",
        langfuse_public_key="",
        langfuse_secret_key="",
        api_env="development",
    )
    mock_exporter = MagicMock()
    mock_processor = MagicMock()

    with (
        patch(
            "pathfinder.ai.orchestration.observability.get_settings",
            return_value=mock_settings,
        ),
        patch(
            "pathfinder.ai.orchestration.observability.HttpSpanExporter",
            return_value=mock_exporter,
        ) as http_exporter_cls,
        patch(
            "pathfinder.ai.orchestration.observability.BatchSpanProcessor",
            return_value=mock_processor,
        ),
    ):
        provider = _configure_exporters()

    assert provider is not None
    http_exporter_cls.assert_called_once_with(
        endpoint="http://localhost:4318/v1/traces"
    )
