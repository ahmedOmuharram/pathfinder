from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    UserPromptPart,
)
from shared_py.stream_events import (
    CustomEvent,
    MessagesCompleteEvent,
    MessagesPartialEvent,
    StreamEvent,
)

from pathfinder.ai.graph.nodes import (
    _convert_assistant_parts,
    _emit_event,
    _extract_latest_assistant_prose,
    discovery_node,
    execution_node,
    model_id,
    planning_node,
    scoping_node,
    supervisor_node,
    verification_node,
)


def test_model_id_handles_string_models() -> None:
    agent: Agent[None, str] = Agent(
        "openai:gpt-4.1-mini",
        output_type=str,
        name="t",
        defer_model_check=True,
    )
    assert model_id(agent) == "openai:gpt-4.1-mini"


def test_model_id_returns_empty_when_no_model() -> None:
    agent: Agent[None, str] = Agent(
        output_type=str, name="t", defer_model_check=True,
    )
    assert model_id(agent) == ""


def test_phase_node_functions_exist() -> None:
    assert callable(scoping_node)
    assert callable(discovery_node)
    assert callable(planning_node)
    assert callable(execution_node)
    assert callable(verification_node)
    assert callable(supervisor_node)


def test_extract_latest_assistant_prose_returns_last_response_text() -> None:
    msgs = [
        ModelResponse(parts=[TextPart(content="first response")]),
        ModelRequest(parts=[UserPromptPart(content="user reply")]),
        ModelResponse(parts=[TextPart(content="second response")]),
    ]
    assert _extract_latest_assistant_prose(msgs) == "second response"


def test_extract_latest_assistant_prose_handles_empty() -> None:
    assert _extract_latest_assistant_prose([]) == ""


def test_extract_latest_assistant_prose_skips_blank_text() -> None:
    msgs = [
        ModelResponse(parts=[TextPart(content="real prose")]),
        ModelResponse(parts=[TextPart(content="   ")]),
    ]
    assert _extract_latest_assistant_prose(msgs) == "real prose"


def test_convert_assistant_parts_text_only() -> None:
    msgs = [ModelResponse(parts=[TextPart(content="hello")])]
    parts = _convert_assistant_parts(msgs)
    assert parts == [{"type": "text", "text": "hello", "state": "done"}]


def test_convert_assistant_parts_with_tool_call() -> None:
    msgs = [
        ModelResponse(
            parts=[
                TextPart(content="thinking"),
                ToolCallPart(
                    tool_name="search_genes",
                    args={"term": "PfATP4"},
                    tool_call_id="call-1",
                ),
            ]
        )
    ]
    parts = _convert_assistant_parts(msgs)
    assert parts == [
        {"type": "text", "text": "thinking", "state": "done"},
        {
            "type": "tool-search_genes",
            "toolCallId": "call-1",
            "state": "input-available",
            "input": {"term": "PfATP4"},
            "providerExecuted": False,
        },
    ]


def test_convert_assistant_parts_drops_final_result_tool_calls() -> None:
    msgs = [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"to": "scoping"},
                    tool_call_id="sup-1",
                ),
                TextPart(content="prose"),
            ]
        )
    ]
    parts = _convert_assistant_parts(msgs)
    assert parts == [{"type": "text", "text": "prose", "state": "done"}]


def test_convert_assistant_parts_with_reasoning() -> None:
    msgs = [
        ModelResponse(
            parts=[
                ThinkingPart(content="reasoned step"),
                TextPart(content="answer"),
            ]
        )
    ]
    parts = _convert_assistant_parts(msgs)
    assert parts == [
        {"type": "reasoning", "text": "reasoned step", "state": "done"},
        {"type": "text", "text": "answer", "state": "done"},
    ]


def test_convert_assistant_parts_skips_request_messages() -> None:
    msgs = [
        ModelRequest(parts=[UserPromptPart(content="user input")]),
        ModelResponse(parts=[TextPart(content="reply")]),
    ]
    parts = _convert_assistant_parts(msgs)
    assert parts == [{"type": "text", "text": "reply", "state": "done"}]


def test_emit_event_writes_camelcase_dump() -> None:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    event: StreamEvent = MessagesPartialEvent(
        message_id="msg-1", delta="hi",
    )
    _emit_event(writer, event)

    assert len(captured) == 1
    payload = captured[0]
    assert "stream_event" in payload
    dumped = payload["stream_event"]
    assert dumped["type"] == "messages/partial"
    assert dumped["messageId"] == "msg-1"
    assert dumped["delta"] == "hi"


def test_emit_event_writes_custom_event() -> None:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    event: StreamEvent = CustomEvent(
        kind="data-phase-start",
        data={"phase": "scoping", "traceId": "t-1", "model": "opus"},
    )
    _emit_event(writer, event)

    dumped = captured[0]["stream_event"]
    assert dumped["type"] == "custom"
    assert dumped["kind"] == "data-phase-start"
    assert dumped["data"]["phase"] == "scoping"


def test_emit_event_messages_complete_passthrough() -> None:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    event: StreamEvent = MessagesCompleteEvent(
        message_id="msg-2",
        role="ai",
        content="final answer",
    )
    _emit_event(writer, event)

    dumped = captured[0]["stream_event"]
    assert dumped["type"] == "messages/complete"
    assert dumped["messageId"] == "msg-2"
    assert dumped["content"] == "final answer"
