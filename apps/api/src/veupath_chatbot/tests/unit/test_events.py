"""Unit tests for the event emission and projection module."""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from veupath_chatbot.platform.events import (
    _project_event,
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
    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == f"stream:{stream_id}"
    fields = call_args[0][1]
    assert fields["type"] == b"user_message"
    assert fields["op"] == b"op_123"


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
    await emit(
        mock_redis,
        stream_id,
        "op_123",
        "strategy_meta",
        {"name": "My Strategy", "recordType": "gene"},
        session=mock_session,
    )

    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()


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
async def test_graph_plan_event_updates_step_count(mock_redis, mock_session):
    """A graph_plan event must update both plan AND step_count in the projection.

    Regression test: previously graph_plan only set plan but never computed
    step_count, causing the sidebar to show stale (usually 0) step counts
    after the AI builds a strategy.
    """
    plan = {
        "recordType": "gene",
        "root": {
            "searchName": "GenesBooleanQuestion",
            "operator": "INTERSECT",
            "id": "step3",
            "primaryInput": {
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "kinase"},
                "id": "step1",
            },
            "secondaryInput": {
                "searchName": "GenesByTextSearch",
                "parameters": {"text_expression": "protease"},
                "id": "step2",
            },
        },
    }

    stream_id = str(uuid4())
    await _project_event(
        mock_session,
        stream_id,
        "graph_plan",
        {"plan": plan, "name": "Test Strategy"},
        "1709234567890-0",
    )

    # Inspect the UPDATE values passed to session.execute()
    stmt = mock_session.execute.call_args[0][0]
    # Extract column names from the compiled values
    col_names = {c.key for c in stmt._values if hasattr(c, "key")}

    assert "step_count" in col_names, (
        f"graph_plan event did not update step_count. Columns: {col_names}"
    )

    # Verify the step_count value is correct (3 steps in our plan)
    step_count_bind = next(
        v
        for c, v in stmt._values.items()
        if hasattr(c, "key") and c.key == "step_count"
    )
    # SQLAlchemy wraps literal values in BindParameter; extract .value
    step_count_val = getattr(step_count_bind, "value", step_count_bind)
    assert step_count_val == 3, f"Expected step_count=3, got {step_count_val}"


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
