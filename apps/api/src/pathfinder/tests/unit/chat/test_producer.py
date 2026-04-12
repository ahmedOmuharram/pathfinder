"""Unit tests for top-level chat trace payload helpers."""

from datetime import UTC, datetime
from uuid import uuid4

from pathfinder.domain.strategy.plan_actions import PlanActionContext
from pathfinder.services.chat.producer import _trace_input_payload
from pathfinder.services.chat.types import ChatTurnConfig, TurnIdentity


def test_trace_input_payload_wraps_chat_message_in_turn_envelope() -> None:
    turn = TurnIdentity(
        stream_id_str="stream-1",
        site_id="plasmodb",
        user_id=uuid4(),
        model_message="Find membrane transporters",
    )

    payload = _trace_input_payload(turn, ChatTurnConfig())

    assert payload == {
        "kind": "chat_message",
        "siteId": "plasmodb",
        "streamId": "stream-1",
        "message": "Find membrane transporters",
    }


def test_trace_input_payload_includes_structured_chat_metadata() -> None:
    turn = TurnIdentity(
        stream_id_str="stream-1",
        site_id="plasmodb",
        user_id=uuid4(),
        model_message="Find membrane transporters",
    )

    payload = _trace_input_payload(
        turn,
        ChatTurnConfig(
            metadata={
                "regenerateOfTraceId": "trace_123",
                "regenerateOfMessageId": "msg_456",
            }
        ),
    )

    assert payload == {
        "kind": "chat_message",
        "siteId": "plasmodb",
        "streamId": "stream-1",
        "message": "Find membrane transporters",
        "metadata": {
            "regenerateOfTraceId": "trace_123",
            "regenerateOfMessageId": "msg_456",
        },
    }


def test_trace_input_payload_wraps_plan_action_with_timing_context() -> None:
    turn = TurnIdentity(
        stream_id_str="stream-2",
        site_id="plasmodb",
        user_id=uuid4(),
        model_message="",
    )
    presented_at = datetime(2026, 4, 10, 20, 15, tzinfo=UTC)
    approved_at = datetime(2026, 4, 10, 20, 18, tzinfo=UTC)

    payload = _trace_input_payload(
        turn,
        ChatTurnConfig(
            plan_action=PlanActionContext(
                action="approve",
                plan_id="plan_123",
                source_trace_id="trace_abc",
                source_message_group_id="group_abc",
                source="plan_panel",
                answered_question_ids=["q1", "q2"],
                edited_params=["step_a.threshold"],
                presented_at=presented_at,
                approved_at=approved_at,
                approval_wait_ms=180000,
            )
        ),
    )

    assert payload == {
        "kind": "plan_action",
        "siteId": "plasmodb",
        "streamId": "stream-2",
        "planAction": {
            "action": "approve",
            "planId": "plan_123",
            "sourceTraceId": "trace_abc",
            "sourceMessageGroupId": "group_abc",
            "source": "plan_panel",
            "answeredQuestionIds": ["q1", "q2"],
            "editedParams": ["step_a.threshold"],
            "presentedAt": presented_at.isoformat(),
            "approvedAt": approved_at.isoformat(),
            "approvalWaitMs": 180000,
        },
    }
