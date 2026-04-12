"""Observability helpers for SSE subscriptions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pathfinder.platform.logging import get_logger
from pathfinder.platform.metrics import (
    sse_active_subscriptions,
    sse_disconnects,
    sse_events_sent,
    sse_keepalives_sent,
    sse_subscription_duration_s,
    sse_subscriptions,
)

logger = get_logger(__name__)


def _surface_for_operation_type(operation_type: str) -> str:
    if operation_type == "chat":
        return "chat"
    if operation_type in {"experiment", "batch", "benchmark", "seed"}:
        return "workbench"
    return operation_type


@dataclass
class SseSubscriptionTelemetry:
    """Mutable telemetry for one SSE subscription."""

    operation_id: str
    operation_type: str
    stream_key: str
    resumed: bool
    last_event_id: str | None = None
    started_monotonic: float = field(default_factory=time.monotonic)
    events_sent: int = 0
    keepalives_sent: int = 0
    terminal_event_type: str | None = None
    disconnect_reason: str | None = None

    @property
    def stream_kind(self) -> str:
        return "operation" if self.stream_key.startswith("op:") else "conversation"

    def metric_attrs(self) -> dict[str, str]:
        return {
            "operation_type": self.operation_type,
            "stream_kind": self.stream_kind,
            "resumed": str(self.resumed).lower(),
            "surface": _surface_for_operation_type(self.operation_type),
        }

    def record_event(self, event_type: str) -> None:
        self.events_sent += 1
        sse_events_sent.add(1, {**self.metric_attrs(), "event_type": event_type})

    def record_keepalive(self) -> None:
        self.keepalives_sent += 1
        sse_keepalives_sent.add(1, self.metric_attrs())

    def mark_terminal_event(self, event_type: str) -> None:
        self.terminal_event_type = event_type
        self.disconnect_reason = "terminal_event"

    def mark_disconnect(self, reason: str) -> None:
        if self.disconnect_reason is None:
            self.disconnect_reason = reason


def start_sse_subscription(telemetry: SseSubscriptionTelemetry) -> None:
    """Record the opening of an SSE subscription."""
    attrs = telemetry.metric_attrs()
    sse_subscriptions.add(1, attrs)
    sse_active_subscriptions.add(1, attrs)
    logger.info(
        "SSE subscription opened",
        operation_type=telemetry.operation_type,
        stream_kind=telemetry.stream_kind,
        resumed=telemetry.resumed,
        last_event_id=telemetry.last_event_id,
    )


def finish_sse_subscription(telemetry: SseSubscriptionTelemetry) -> None:
    """Record the end of an SSE subscription."""
    attrs = telemetry.metric_attrs()
    duration_s = time.monotonic() - telemetry.started_monotonic
    reason = telemetry.disconnect_reason or "completed"
    sse_active_subscriptions.add(-1, attrs)
    sse_subscription_duration_s.record(duration_s, {**attrs, "reason": reason})
    sse_disconnects.add(1, {**attrs, "reason": reason})
    logger.info(
        "SSE subscription closed",
        operation_type=telemetry.operation_type,
        stream_kind=telemetry.stream_kind,
        resumed=telemetry.resumed,
        disconnect_reason=reason,
        terminal_event_type=telemetry.terminal_event_type,
        duration_ms=round(duration_s * 1000),
        events_sent=telemetry.events_sent,
        keepalives_sent=telemetry.keepalives_sent,
        last_event_id=telemetry.last_event_id,
    )
