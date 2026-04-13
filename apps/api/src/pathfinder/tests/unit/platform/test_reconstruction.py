"""Unit tests for Redis stream reconstruction."""

import json

from pathfinder.ai.context.reconstruction import extract_resume_phase_from_entries
from pathfinder.platform.reconstruction import (
    _process_stream_event,
    _TurnAccumulator,
)
from pathfinder.platform.types import JSONObject


def test_reconstruction_keeps_phase_level_assistant_messages_separate() -> None:
    turn = _TurnAccumulator()
    messages: list[JSONObject] = []

    _process_stream_event("message_start", {}, "1000-0", turn, messages)
    _process_stream_event(
        "model_selected",
        {
            "pipeline": {
                "scoping": {"modelId": "model-scoping", "reasoningEffort": "low"},
                "discovery": {"modelId": "model-discovery", "reasoningEffort": "low"},
                "planning": {"modelId": "model-planning", "reasoningEffort": "medium"},
                "execution": {"modelId": "model-execution", "reasoningEffort": "medium"},
                "verification": {"modelId": "model-verification", "reasoningEffort": "high"},
            }
        },
        "1001-0",
        turn,
        messages,
    )
    _process_stream_event(
        "phase_change",
        {
            "phase": "execution",
            "status": "started",
            "messageId": "exec-msg",
            "messageGroupId": "turn-1",
        },
        "1002-0",
        turn,
        messages,
    )
    _process_stream_event(
        "tool_call_start",
        {"id": "tool-1", "name": "create_leaf_step", "arguments": {}},
        "1003-0",
        turn,
        messages,
    )
    _process_stream_event(
        "tool_call_end",
        {"id": "tool-1", "result": "{\"ok\":true}"},
        "1004-0",
        turn,
        messages,
    )
    _process_stream_event(
        "assistant_message",
        {
            "messageId": "exec-msg",
            "messageGroupId": "turn-1",
            "phase": "execution",
            "content": "Executed the approved plan.",
        },
        "1005-0",
        turn,
        messages,
    )
    _process_stream_event(
        "phase_change",
        {
            "phase": "verification",
            "status": "started",
            "messageId": "verify-msg",
            "messageGroupId": "turn-1",
        },
        "1006-0",
        turn,
        messages,
    )
    _process_stream_event(
        "assistant_message",
        {
            "messageId": "verify-msg",
            "messageGroupId": "turn-1",
            "phase": "verification",
            "content": "Verification complete.",
        },
        "1007-0",
        turn,
        messages,
    )

    assert len(messages) == 2

    execution_msg = messages[0]
    verification_msg = messages[1]

    assert execution_msg["messageId"] == "exec-msg"
    assert execution_msg["messageGroupId"] == "turn-1"
    assert execution_msg["phase"] == "execution"
    assert execution_msg["modelId"] == "model-execution"
    assert execution_msg["toolCalls"] == [
        {
            "id": "tool-1",
            "name": "create_leaf_step",
            "arguments": {},
            "result": "{\"ok\":true}",
        }
    ]

    assert verification_msg["messageId"] == "verify-msg"
    assert verification_msg["messageGroupId"] == "turn-1"
    assert verification_msg["phase"] == "verification"
    assert verification_msg["modelId"] == "model-verification"
    assert "toolCalls" not in verification_msg


def test_extract_resume_phase_from_entries_uses_latest_awaiting_input() -> None:
    entries = [
        (
            "1000-0",
            {
                "type": "phase_change",
                "data": json.dumps(
                    {
                        "phase": "discovery",
                        "status": "awaiting_input",
                        "messageId": "discovery-msg",
                    }
                ),
            },
        ),
        (
            "1001-0",
            {
                "type": "phase_change",
                "data": json.dumps(
                    {
                        "phase": "planning",
                        "status": "started",
                        "messageId": "planning-msg",
                    }
                ),
            },
        ),
    ]

    assert extract_resume_phase_from_entries(entries) is None

    entries.append(
        (
            "1002-0",
            {
                "type": "phase_change",
                "data": json.dumps(
                    {
                        "phase": "discovery",
                        "status": "awaiting_input",
                        "messageId": "discovery-msg-2",
                    }
                ),
            },
        )
    )

    assert extract_resume_phase_from_entries(entries) == "discovery"


def test_plan_presented_event_does_not_crash() -> None:
    turn = _TurnAccumulator()
    messages: list[JSONObject] = []

    _process_stream_event("message_start", {}, "1000-0", turn, messages)
    _process_stream_event(
        "plan_presented",
        {"plan": {"id": "plan_abc123", "title": "Test Plan", "status": "presented"}},
        "1001-0",
        turn,
        messages,
    )
    assert len(messages) == 0


def test_plan_approved_event_does_not_crash() -> None:
    turn = _TurnAccumulator()
    messages: list[JSONObject] = []

    _process_stream_event("message_start", {}, "1000-0", turn, messages)
    _process_stream_event(
        "plan_approved",
        {"planId": "plan_abc123", "plan": {}},
        "1002-0",
        turn,
        messages,
    )
    assert len(messages) == 0


def test_plan_updated_event_does_not_crash() -> None:
    turn = _TurnAccumulator()
    messages: list[JSONObject] = []

    _process_stream_event("message_start", {}, "1000-0", turn, messages)
    _process_stream_event(
        "plan_updated",
        {"planId": "plan_abc123", "updates": {"status": "executing"}},
        "1003-0",
        turn,
        messages,
    )
    assert len(messages) == 0
