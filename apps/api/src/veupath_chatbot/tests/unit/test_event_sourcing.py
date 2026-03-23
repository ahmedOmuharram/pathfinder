"""Event sourcing tests using fakeredis for realistic Redis stream operations.

Complements test_events.py (which uses AsyncMock) by exercising actual
Redis stream commands (XADD, XRANGE) against an in-process fake.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import fakeredis
import pytest

from veupath_chatbot.platform.events import (
    emit,
    read_stream_messages,
    read_stream_thinking,
)


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis()
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_emit_creates_stream_entry(redis):
    stream_id = str(uuid4())
    entry_id = await emit(redis, stream_id, "op_1", "user_message", {"content": "hi"})
    assert "-" in entry_id

    entries = await redis.xrange(f"stream:{stream_id}")
    assert len(entries) == 1
    _, fields = entries[0]
    assert fields[b"type"] == b"user_message"
    assert fields[b"op"] == b"op_1"
    data = json.loads(fields[b"data"])
    assert data["content"] == "hi"


@pytest.mark.asyncio
async def test_emit_multiple_events_ordered(redis):
    stream_id = str(uuid4())
    id1 = await emit(redis, stream_id, "op_1", "user_message", {"content": "first"})
    id2 = await emit(
        redis, stream_id, "op_1", "assistant_message", {"content": "second"}
    )

    entries = await redis.xrange(f"stream:{stream_id}")
    assert len(entries) == 2
    assert id1 < id2


@pytest.mark.asyncio
async def test_emit_with_none_operation_id(redis):
    stream_id = str(uuid4())
    entry_id = await emit(redis, stream_id, None, "user_message", {"content": "hi"})
    assert "-" in entry_id

    entries = await redis.xrange(f"stream:{stream_id}")
    _, fields = entries[0]
    assert fields[b"op"] == b""


@pytest.mark.asyncio
async def test_round_trip_user_and_assistant_messages(redis):
    stream_id = str(uuid4())
    await emit(
        redis,
        stream_id,
        "op_1",
        "user_message",
        {"content": "hello", "messageId": "m1"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "hi back", "messageId": "m2"},
    )

    messages = await read_stream_messages(redis, stream_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hi back"


@pytest.mark.asyncio
async def test_tool_calls_aggregated_into_assistant_message(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis,
        stream_id,
        "op_1",
        "user_message",
        {"content": "find genes", "messageId": "m1"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "tool_call_start",
        {
            "id": "tc1",
            "name": "search_for_searches",
            "arguments": {"query": "kinase"},
        },
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "tool_call_end",
        {"id": "tc1", "result": "found 5 results"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "I found genes", "messageId": "m2"},
    )
    await emit(redis, stream_id, "op_1", "message_end", {})

    messages = await read_stream_messages(redis, stream_id)
    assert len(messages) == 2

    assistant = messages[1]
    assert assistant["role"] == "assistant"
    assert len(assistant["toolCalls"]) == 1
    tc = assistant["toolCalls"][0]
    assert tc["name"] == "search_for_searches"
    assert isinstance(tc["arguments"], dict)
    assert tc["arguments"]["query"] == "kinase"
    assert tc["result"] == "found 5 results"


@pytest.mark.asyncio
async def test_citations_aggregated_into_assistant_message(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis,
        stream_id,
        "op_1",
        "citations",
        {"citations": [{"url": "http://example.com", "title": "Paper"}]},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "Here are results", "messageId": "m1"},
    )
    await emit(redis, stream_id, "op_1", "message_end", {})

    messages = await read_stream_messages(redis, stream_id)
    assert len(messages) == 1
    assert messages[0]["citations"][0]["url"] == "http://example.com"


@pytest.mark.asyncio
async def test_reasoning_aggregated_into_assistant_message(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis,
        stream_id,
        "op_1",
        "reasoning",
        {"reasoning": "User wants kinase genes"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "Found them", "messageId": "m1"},
    )
    await emit(redis, stream_id, "op_1", "message_end", {})

    messages = await read_stream_messages(redis, stream_id)
    assert messages[0]["reasoning"] == "User wants kinase genes"


@pytest.mark.asyncio
async def test_multiple_turns_independent(redis):
    stream_id = str(uuid4())

    # Turn 1
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis, stream_id, "op_1", "user_message", {"content": "q1", "messageId": "m1"}
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "tool_call_start",
        {"id": "tc1", "name": "tool_a", "arguments": {}},
    )
    await emit(redis, stream_id, "op_1", "tool_call_end", {"id": "tc1", "result": "r1"})
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "a1", "messageId": "m2"},
    )
    await emit(redis, stream_id, "op_1", "message_end", {})

    # Turn 2
    await emit(redis, stream_id, "op_2", "message_start", {})
    await emit(
        redis, stream_id, "op_2", "user_message", {"content": "q2", "messageId": "m3"}
    )
    await emit(
        redis,
        stream_id,
        "op_2",
        "assistant_message",
        {"content": "a2", "messageId": "m4"},
    )
    await emit(redis, stream_id, "op_2", "message_end", {})

    messages = await read_stream_messages(redis, stream_id)
    assert len(messages) == 4

    # Turn 1 assistant should have tool calls
    assert "toolCalls" in messages[1]
    assert len(messages[1]["toolCalls"]) == 1

    # Turn 2 assistant should NOT have tool calls from turn 1
    assert "toolCalls" not in messages[3]


@pytest.mark.asyncio
async def test_empty_stream_returns_empty_messages(redis):
    messages = await read_stream_messages(redis, str(uuid4()))
    assert messages == []


@pytest.mark.asyncio
async def test_thinking_no_events_returns_none(redis):
    result = await read_stream_thinking(redis, str(uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_thinking_completed_turn_returns_none(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis, stream_id, "op_1", "tool_call_start", {"id": "tc1", "name": "search"}
    )
    await emit(redis, stream_id, "op_1", "tool_call_end", {"id": "tc1"})
    await emit(redis, stream_id, "op_1", "message_end", {})

    result = await read_stream_thinking(redis, stream_id)
    assert result is None


@pytest.mark.asyncio
async def test_thinking_active_tool_calls(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis,
        stream_id,
        "op_1",
        "tool_call_start",
        {"id": "tc1", "name": "search_for_searches"},
    )

    result = await read_stream_thinking(redis, stream_id)
    assert result is not None
    assert len(result["toolCalls"]) == 1
    assert result["toolCalls"][0]["name"] == "search_for_searches"


@pytest.mark.asyncio
async def test_thinking_mixed_completed_and_active(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis, stream_id, "op_1", "tool_call_start", {"id": "tc1", "name": "done_tool"}
    )
    await emit(redis, stream_id, "op_1", "tool_call_end", {"id": "tc1"})
    await emit(
        redis,
        stream_id,
        "op_1",
        "tool_call_start",
        {"id": "tc2", "name": "active_tool"},
    )

    result = await read_stream_thinking(redis, stream_id)
    assert result is not None
    assert len(result["toolCalls"]) == 1
    assert result["toolCalls"][0]["name"] == "active_tool"


@pytest.mark.asyncio
async def test_subkani_events_aggregated(redis):
    stream_id = str(uuid4())
    await emit(redis, stream_id, "op_1", "message_start", {})
    await emit(
        redis, stream_id, "op_1", "user_message", {"content": "hi", "messageId": "m1"}
    )
    await emit(redis, stream_id, "op_1", "subkani_task_start", {"task": "research"})
    await emit(
        redis,
        stream_id,
        "op_1",
        "subkani_tool_call_start",
        {"task": "research", "id": "stc1", "name": "web_search"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "subkani_tool_call_end",
        {"task": "research", "id": "stc1", "result": "found"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "subkani_task_end",
        {"task": "research", "status": "done"},
    )
    await emit(
        redis,
        stream_id,
        "op_1",
        "assistant_message",
        {"content": "result", "messageId": "m2"},
    )
    await emit(redis, stream_id, "op_1", "message_end", {})

    messages = await read_stream_messages(redis, stream_id)
    assistant = messages[1]
    assert "subKaniActivity" in assistant
    activity = assistant["subKaniActivity"]
    assert "research" in activity["calls"]
    assert activity["status"]["research"] == "done"
    assert activity["calls"]["research"][0]["result"] == "found"


@pytest.mark.asyncio
async def test_emit_with_projection(redis):
    """emit() with a session triggers DB projection (mock the session)."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    stream_id = str(uuid4())
    await emit(
        redis,
        stream_id,
        "op_1",
        "strategy_meta",
        {"name": "Test"},
        session=mock_session,
    )

    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()

    # Event should still be in Redis
    entries = await redis.xrange(f"stream:{stream_id}")
    assert len(entries) == 1
