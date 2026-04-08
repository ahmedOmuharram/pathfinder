"""Tests for platform.metrics instrument definitions."""

from pathfinder.platform.metrics import (
    phase_duration_s,
    pipeline_errors,
    pipeline_runs,
    token_usage,
    wdk_request_duration_s,
)


def test_counters_accept_add_without_provider() -> None:
    """Counters record to the no-op sink when no MeterProvider is configured."""
    pipeline_runs.add(1, {"intent": "new_strategy", "outcome": "completed", "model": "test"})
    token_usage.add(100, {"model": "test", "type": "input"})
    pipeline_errors.add(1, {"error_type": "ValueError"})


def test_histograms_accept_record_without_provider() -> None:
    """Histograms record to the no-op sink when no MeterProvider is configured."""
    phase_duration_s.record(1.5, {"phase": "discovery", "intent": "new_strategy"})
    wdk_request_duration_s.record(0.3, {"method": "GET", "outcome": "ok"})
