"""Tests for Langfuse product action recording."""

from unittest.mock import MagicMock, patch

from pathfinder.platform.langfuse.actions import (
    ProductActionEvent,
    record_product_action,
)


def test_record_product_action_noop_when_langfuse_disabled() -> None:
    with patch(
        "pathfinder.platform.langfuse.actions.get_langfuse",
        return_value=None,
    ):
        record_product_action(
            ProductActionEvent(
                action="plan_approve",
                trace_id="trace-123",
                stream_id="stream-abc",
                strategy_id="strategy-abc",
                plan_id="plan-123",
            )
        )


def test_record_product_action_creates_event_with_trace_context() -> None:
    mock_client = MagicMock()
    with patch(
        "pathfinder.platform.langfuse.actions.get_langfuse",
        return_value=mock_client,
    ):
        record_product_action(
            ProductActionEvent(
                action="plan_suggest_changes",
                trace_id="trace-123",
                stream_id="stream-abc",
                strategy_id="strategy-abc",
                plan_id="plan-123",
                message_group_id="group-1",
                metadata={"source": "plan_panel", "param_edit_count": 2},
            )
        )

    mock_client.create_event.assert_called_once_with(
        trace_context={"trace_id": "trace-123"},
        name="product.plan_suggest_changes",
        input={
            "action": "plan_suggest_changes",
            "stream_id": "stream-abc",
            "strategy_id": "strategy-abc",
            "plan_id": "plan-123",
            "message_group_id": "group-1",
        },
        metadata={
            "stream_id": "stream-abc",
            "strategy_id": "strategy-abc",
            "plan_id": "plan-123",
            "message_group_id": "group-1",
            "source": "plan_panel",
            "param_edit_count": 2,
        },
    )


def test_record_product_action_handles_exception() -> None:
    mock_client = MagicMock()
    mock_client.create_event.side_effect = OSError("Network error")
    with patch(
        "pathfinder.platform.langfuse.actions.get_langfuse",
        return_value=mock_client,
    ):
        record_product_action(
            ProductActionEvent(
                action="undo_turn",
                stream_id="stream-err",
                entry_id="1709234567890-0",
            )
        )
