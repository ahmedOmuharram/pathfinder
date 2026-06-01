"""Tests for SSE subscription observability helpers."""

from unittest.mock import patch

from pathfinder.transport.http.sse_observability import (
    SseSubscriptionTelemetry,
    finish_sse_subscription,
    start_sse_subscription,
)


def test_sse_subscription_records_lifecycle_metrics() -> None:
    telemetry = SseSubscriptionTelemetry(
        operation_id="op_123",
        operation_type="chat",
        stream_key="stream:abc",
        resumed=True,
        last_event_id="1700-1",
    )
    telemetry.started_monotonic = 10.0

    with (
        patch(
            "pathfinder.transport.http.sse_observability.sse_subscriptions"
        ) as mock_started,
        patch(
            "pathfinder.transport.http.sse_observability.sse_active_subscriptions"
        ) as mock_active,
        patch(
            "pathfinder.transport.http.sse_observability.sse_events_sent"
        ) as mock_events,
        patch(
            "pathfinder.transport.http.sse_observability.sse_keepalives_sent"
        ) as mock_keepalives,
        patch(
            "pathfinder.transport.http.sse_observability.sse_subscription_duration_s"
        ) as mock_duration,
        patch(
            "pathfinder.transport.http.sse_observability.sse_disconnects"
        ) as mock_disconnects,
        patch("pathfinder.transport.http.sse_observability.logger") as mock_logger,
        patch(
            "pathfinder.transport.http.sse_observability.time.monotonic",
            return_value=13.5,
        ),
    ):
        start_sse_subscription(telemetry)
        telemetry.record_event("assistant_delta")
        telemetry.record_keepalive()
        telemetry.mark_terminal_event("message_end")
        finish_sse_subscription(telemetry)

    base_attrs = {
        "operation_type": "chat",
        "stream_kind": "conversation",
        "resumed": "true",
        "surface": "chat",
    }
    mock_started.add.assert_called_once_with(1, base_attrs)
    assert mock_active.add.call_args_list[0].args == (1, base_attrs)
    assert mock_active.add.call_args_list[1].args == (-1, base_attrs)
    mock_events.add.assert_called_once_with(
        1,
        {**base_attrs, "event_type": "assistant_delta"},
    )
    mock_keepalives.add.assert_called_once_with(1, base_attrs)
    mock_duration.record.assert_called_once_with(
        3.5,
        {**base_attrs, "reason": "terminal_event"},
    )
    mock_disconnects.add.assert_called_once_with(
        1,
        {**base_attrs, "reason": "terminal_event"},
    )
    assert mock_logger.info.call_count == 2
