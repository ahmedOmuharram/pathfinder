from __future__ import annotations

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)
from shared_py.stream_events import (
    MessagesCompleteEvent,
    MessagesPartialEvent,
)

from pathfinder.ai.chat.langgraph_adapter import LangGraphEventAdapter


def test_text_delta_emits_messages_partial() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-1")
    out = list(
        adapter.handle(
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello"))
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], MessagesPartialEvent)
    assert out[0].delta == "Hello"
    assert out[0].message_id == "msg-1"


def test_part_start_text_emits_messages_partial() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-2")
    out = list(adapter.handle(PartStartEvent(index=0, part=TextPart(content="Hi"))))
    assert len(out) == 1
    assert isinstance(out[0], MessagesPartialEvent)
    assert out[0].delta == "Hi"


def test_part_start_text_with_empty_content_emits_nothing() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-empty")
    out = list(adapter.handle(PartStartEvent(index=0, part=TextPart(content=""))))
    assert out == []


def test_thinking_part_start_emits_reasoning_delta() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-think")
    out = list(
        adapter.handle(
            PartStartEvent(index=0, part=ThinkingPart(content="Considering options"))
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], MessagesPartialEvent)
    assert out[0].reasoning_delta == "Considering options"
    assert out[0].delta == ""


def test_thinking_delta_emits_reasoning_delta() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-think-d")
    out = list(
        adapter.handle(
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" more"))
        )
    )
    assert len(out) == 1
    assert isinstance(out[0], MessagesPartialEvent)
    assert out[0].reasoning_delta == " more"


def test_thinking_delta_with_none_content_emits_nothing() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-think-none")
    out = list(
        adapter.handle(
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(signature_delta="sig"))
        )
    )
    assert out == []


def test_tool_call_start_then_delta_buffers_and_emits_partials() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-3")
    out_start = list(
        adapter.handle(
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_call_id="tc-1", tool_name="search", args=""),
            )
        )
    )
    out_delta = list(
        adapter.handle(
            PartDeltaEvent(
                index=1,
                delta=ToolCallPartDelta(tool_call_id="tc-1", args_delta='{"q":'),
            )
        )
    )
    assert len(out_start) == 1
    assert isinstance(out_start[0], MessagesPartialEvent)
    assert out_start[0].tool_call_deltas[0].tool_call_id == "tc-1"
    assert out_start[0].tool_call_deltas[0].tool_name == "search"

    assert len(out_delta) == 1
    assert isinstance(out_delta[0], MessagesPartialEvent)
    assert out_delta[0].tool_call_deltas[0].tool_call_id == "tc-1"
    assert out_delta[0].tool_call_deltas[0].arguments_delta == '{"q":'


def test_tool_call_args_buffer_concatenates_string_deltas() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-buf")
    list(
        adapter.handle(
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_call_id="tc-2", tool_name="t", args=""),
            )
        )
    )
    list(
        adapter.handle(
            PartDeltaEvent(
                index=0,
                delta=ToolCallPartDelta(tool_call_id="tc-2", args_delta='{"a":'),
            )
        )
    )
    list(
        adapter.handle(
            PartDeltaEvent(
                index=0,
                delta=ToolCallPartDelta(tool_call_id="tc-2", args_delta='1}'),
            )
        )
    )
    final = adapter.finalize()
    assert final.tool_calls[0].arguments == {"a": 1}


def test_tool_return_emits_messages_complete() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-4")
    ret_part = ToolReturnPart(
        tool_call_id="tc-1", tool_name="search", content={"results": [1, 2]}
    )
    out = list(adapter.handle(FunctionToolResultEvent(result=ret_part)))
    assert len(out) == 1
    assert isinstance(out[0], MessagesCompleteEvent)
    assert out[0].role == "tool"
    assert out[0].tool_call_id == "tc-1"
    assert out[0].name == "search"
    assert '"results"' in out[0].content


def test_tool_return_with_string_content_passes_through() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-str")
    ret_part = ToolReturnPart(
        tool_call_id="tc-x", tool_name="echo", content="raw text"
    )
    out = list(adapter.handle(FunctionToolResultEvent(result=ret_part)))
    assert len(out) == 1
    assert isinstance(out[0], MessagesCompleteEvent)
    assert out[0].content == "raw text"


def test_function_tool_call_event_emits_nothing() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-fc")
    call_part = ToolCallPart(tool_call_id="tc-fc", tool_name="t", args='{"k":1}')
    out = list(adapter.handle(FunctionToolCallEvent(part=call_part)))
    assert out == []


def test_finalize_produces_completed_message_with_text() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-5")
    list(adapter.handle(PartStartEvent(index=0, part=TextPart(content="Hello "))))
    list(
        adapter.handle(
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="world"))
        )
    )
    final = adapter.finalize()
    assert isinstance(final, MessagesCompleteEvent)
    assert final.role == "ai"
    assert final.content == "Hello world"
    assert final.message_id == "msg-5"
    assert final.tool_calls == []


def test_finalize_includes_completed_tool_calls() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-fin-tc")
    list(
        adapter.handle(
            PartStartEvent(
                index=0,
                part=ToolCallPart(
                    tool_call_id="tc-9", tool_name="search", args='{"q":"malaria"}'
                ),
            )
        )
    )
    final = adapter.finalize()
    assert len(final.tool_calls) == 1
    assert final.tool_calls[0].id == "tc-9"
    assert final.tool_calls[0].name == "search"
    assert final.tool_calls[0].arguments == {"q": "malaria"}


def test_finalize_wraps_non_dict_args_as_value() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-scalar")
    list(
        adapter.handle(
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_call_id="tc-s", tool_name="t", args="42"),
            )
        )
    )
    final = adapter.finalize()
    assert final.tool_calls[0].arguments == {"value": 42}


def test_finalize_includes_reasoning_buffer() -> None:
    adapter = LangGraphEventAdapter(message_id="msg-r")
    list(
        adapter.handle(
            PartStartEvent(index=0, part=ThinkingPart(content="thought one. "))
        )
    )
    list(
        adapter.handle(
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="thought two."))
        )
    )
    final = adapter.finalize()
    assert final.reasoning == "thought one. thought two."
