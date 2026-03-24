"""Unit tests for the event emission and projection module."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from veupath_chatbot.platform.events import (
    emit,
    read_stream_messages,
    read_stream_thinking,
)


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value=b"1709234567890-0")
    redis.xrange = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_emit_writes_to_redis(mock_redis, mock_session):
    stream_id = str(uuid4())
    entry_id = await emit(
        mock_redis,
        stream_id,
        "op_123",
        "user_message",
        {"content": "hello"},
        session=mock_session,
    )

    assert entry_id == "1709234567890-0"


@pytest.mark.asyncio
async def test_emit_without_session_skips_projection(mock_redis):
    entry_id = await emit(
        mock_redis,
        str(uuid4()),
        "op_123",
        "user_message",
        {"content": "hello"},
    )

    assert entry_id == "1709234567890-0"


@pytest.mark.asyncio
async def test_emit_projects_strategy_meta(mock_redis, mock_session):
    stream_id = str(uuid4())
    entry_id = await emit(
        mock_redis,
        stream_id,
        "op_123",
        "strategy_meta",
        {"name": "My Strategy", "recordType": "gene"},
        session=mock_session,
    )

    # emit should return a valid Redis entry ID
    assert entry_id == "1709234567890-0"


@pytest.mark.asyncio
async def test_read_stream_messages(mock_redis):
    mock_redis.xrange.return_value = [
        (
            b"1-0",
            {
                b"op": b"op_1",
                b"type": b"user_message",
                b"data": json.dumps({"messageId": "m1", "content": "hi"}).encode(),
            },
        ),
        (
            b"2-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": json.dumps({"id": "tc1", "name": "search"}).encode(),
            },
        ),
        (
            b"3-0",
            {
                b"op": b"op_1",
                b"type": b"assistant_message",
                b"data": json.dumps(
                    {"messageId": "m2", "content": "hello back"}
                ).encode(),
            },
        ),
    ]

    messages = await read_stream_messages(mock_redis, str(uuid4()))
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hi"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hello back"


@pytest.mark.asyncio
async def test_read_stream_messages_includes_optional_fields(mock_redis):
    mock_redis.xrange.return_value = [
        (
            b"1-0",
            {
                b"op": b"op_1",
                b"type": b"assistant_message",
                b"data": json.dumps(
                    {
                        "messageId": "m1",
                        "content": "result",
                        "citations": [{"url": "http://example.com"}],
                        "toolCalls": [{"id": "tc1", "name": "search"}],
                    }
                ).encode(),
            },
        ),
    ]

    messages = await read_stream_messages(mock_redis, str(uuid4()))
    assert len(messages) == 1
    assert messages[0]["citations"] == [{"url": "http://example.com"}]
    assert messages[0]["toolCalls"] == [{"id": "tc1", "name": "search"}]


@pytest.mark.asyncio
async def test_read_stream_messages_parses_tool_call_arguments(mock_redis):
    """Tool call arguments are stored as JSON strings in Redis but must be dicts."""
    mock_redis.xrange.return_value = [
        (
            b"1-0",
            {
                b"op": b"op_1",
                b"type": b"user_message",
                b"data": json.dumps({"messageId": "m1", "content": "hi"}).encode(),
            },
        ),
        (
            b"2-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": json.dumps(
                    {
                        "id": "tc1",
                        "name": "set_title",
                        "arguments": {"title": "My Strategy"},
                    }
                ).encode(),
            },
        ),
        (
            b"3-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_end",
                b"data": json.dumps({"id": "tc1", "result": "ok"}).encode(),
            },
        ),
        (
            b"4-0",
            {
                b"op": b"op_1",
                b"type": b"assistant_message",
                b"data": json.dumps({"messageId": "m2", "content": "Done!"}).encode(),
            },
        ),
    ]

    messages = await read_stream_messages(mock_redis, str(uuid4()))
    assert len(messages) == 2
    assistant = messages[1]
    assert assistant["toolCalls"] is not None
    assert len(assistant["toolCalls"]) == 1
    tc = assistant["toolCalls"][0]
    # arguments MUST be a dict, not a JSON string
    assert isinstance(tc["arguments"], dict), (
        f"Expected dict, got {type(tc['arguments'])}: {tc['arguments']}"
    )
    assert tc["arguments"]["title"] == "My Strategy"
    assert tc["result"] == "ok"


@pytest.mark.asyncio
async def test_read_stream_messages_handles_dict_arguments(mock_redis):
    """Arguments that are already dicts should pass through unchanged."""
    mock_redis.xrange.return_value = [
        (
            b"1-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": json.dumps(
                    {
                        "id": "tc1",
                        "name": "search",
                        "arguments": {"query": "malaria"},
                    }
                ).encode(),
            },
        ),
        (
            b"2-0",
            {
                b"op": b"op_1",
                b"type": b"assistant_message",
                b"data": json.dumps(
                    {"messageId": "m1", "content": "Found results"}
                ).encode(),
            },
        ),
    ]

    messages = await read_stream_messages(mock_redis, str(uuid4()))
    assert len(messages) == 1
    tc = messages[0]["toolCalls"][0]
    assert isinstance(tc["arguments"], dict)
    assert tc["arguments"]["query"] == "malaria"


@pytest.mark.asyncio
async def test_read_stream_thinking_no_active_turn(mock_redis):
    mock_redis.xrange.return_value = []
    result = await read_stream_thinking(mock_redis, str(uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_read_stream_thinking_completed_turn(mock_redis):
    mock_redis.xrange.return_value = [
        (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
        (
            b"2-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": json.dumps({"id": "tc1", "name": "search"}).encode(),
            },
        ),
        (
            b"3-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_end",
                b"data": json.dumps({"id": "tc1"}).encode(),
            },
        ),
        (b"4-0", {b"op": b"op_1", b"type": b"message_end", b"data": b"{}"}),
    ]

    result = await read_stream_thinking(mock_redis, str(uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_read_stream_thinking_active_tool_calls(mock_redis):
    mock_redis.xrange.return_value = [
        (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
        (
            b"2-0",
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": json.dumps(
                    {"id": "tc1", "name": "search_for_searches"}
                ).encode(),
            },
        ),
    ]

    result = await read_stream_thinking(mock_redis, str(uuid4()))
    assert result is not None
    assert len(result["toolCalls"]) == 1
    assert result["toolCalls"][0]["name"] == "search_for_searches"
