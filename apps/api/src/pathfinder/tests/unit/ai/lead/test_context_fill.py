"""A running dispatch reports the last request's input size and the model's window."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.usage import RunUsage

from pathfinder.ai.lead.sub_agent_stream import (
    _ContextMeter,
    _emit_running_sub_agent_usage,
)
from pathfinder.ai.models.catalog import get_model_entry


class _Collector:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)

    @property
    def sub_agent_calls(self) -> list[dict[str, Any]]:
        return [
            p["chunk"]["data"]
            for p in self.payloads
            if p["chunk"]["type"] == "data-sub-agent-call"
        ]


def test_context_meter_reports_each_request_input_delta() -> None:
    meter = _ContextMeter()
    usage = RunUsage(input_tokens=1000)

    assert meter.last_request_input(usage) == 1000

    usage.input_tokens = 2500
    assert meter.last_request_input(usage) == 1500


def test_context_meter_floors_a_reset_at_zero() -> None:
    """A history reset lowers the cumulative count; the bar reads zero, not negative."""
    meter = _ContextMeter()
    usage = RunUsage(input_tokens=5000)
    meter.last_request_input(usage)

    usage.input_tokens = 3000
    assert meter.last_request_input(usage) == 0


def test_running_emission_carries_the_last_request_and_the_window() -> None:
    collector = _Collector()
    meter = _ContextMeter()
    usage = RunUsage(input_tokens=1000, output_tokens=10)

    _emit_running_sub_agent_usage(collector, "frame", "call_frame_1", usage, meter)
    usage.input_tokens = 2500
    _emit_running_sub_agent_usage(collector, "frame", "call_frame_1", usage, meter)

    first, second = collector.sub_agent_calls
    assert first["contextTokens"] == 1000
    assert second["contextTokens"] == 1500
    entry = get_model_entry(first["modelId"])
    assert entry is not None
    assert first["contextWindow"] == entry.context_size
    assert second["contextWindow"] == entry.context_size


def test_unknown_model_reports_no_window(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _Collector()
    monkeypatch.setattr(
        "pathfinder.ai.lead.sub_agent_stream.phase_default_model_id",
        lambda role: "nosuchprovider:nosuchmodel",
    )

    _emit_running_sub_agent_usage(
        collector,
        "frame",
        "call_frame_1",
        RunUsage(input_tokens=900),
        _ContextMeter(),
    )

    payload = collector.sub_agent_calls[0]
    assert payload["contextWindow"] == 0
    assert payload["contextTokens"] == 900


def test_context_meter_repeats_the_size_across_one_requests_emissions() -> None:
    """Parallel tool calls emit twice for one request; the bar must not drop to 0."""
    meter = _ContextMeter()
    usage = RunUsage(input_tokens=1000)

    assert meter.last_request_input(usage) == 1000
    assert meter.last_request_input(usage) == 1000

    usage.input_tokens = 2500
    assert meter.last_request_input(usage) == 1500
