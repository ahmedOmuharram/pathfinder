"""Test that message_end token metrics persist through Redis round-trip.

Verifies that read_stream_messages() correctly reconstructs all TokenUsage
fields from Redis stream events — including the new fields added for
cost tracking, cached tokens, and sub-kani metrics.
"""

import json

from veupath_chatbot.platform.events import read_stream_messages


def _make_redis_entries(
    events: list[tuple[str, dict]],
) -> list[tuple[bytes, dict[bytes, bytes]]]:
    """Build fake Redis XRANGE output from (event_type, data) pairs."""
    entries = []
    for i, (event_type, data) in enumerate(events):
        entry_id = f"1709234567{i:03d}-0".encode()
        fields = {
            b"op": b"op_test",
            b"type": event_type.encode(),
            b"data": json.dumps(data).encode(),
        }
        entries.append((entry_id, fields))
    return entries


class FakeRedis:
    """Minimal fake Redis that returns pre-built XRANGE results."""

    def __init__(self, entries):
        self._entries = entries

    async def xrange(self, key):
        return self._entries


async def test_message_end_fields_persist_through_round_trip():
    """All new TokenUsage fields survive: emit → Redis → read_stream_messages."""
    events = [
        ("message_start", {}),
        ("model_selected", {"modelId": "openai/gpt-4.1-nano"}),
        ("user_message", {"content": "hi", "messageId": "u1"}),
        ("assistant_message", {"content": "hello", "messageId": "a1"}),
        (
            "message_end",
            {
                "promptTokens": 12000,
                "completionTokens": 50,
                "totalTokens": 12050,
                "cachedTokens": 8000,
                "toolCallCount": 0,
                "registeredToolCount": 42,
                "llmCallCount": 3,
                "subKaniPromptTokens": 5000,
                "subKaniCompletionTokens": 200,
                "subKaniCallCount": 2,
                "estimatedCostUsd": 0.042,
                "modelId": "openai/gpt-4.1-nano",
            },
        ),
    ]

    redis = FakeRedis(_make_redis_entries(events))
    messages = await read_stream_messages(redis, "test-stream")

    # Find the assistant message (tokenUsage is attached to it)
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1

    tu = assistant_msgs[0].get("tokenUsage")
    assert tu is not None, "tokenUsage missing from assistant message"

    # Verify ALL fields persisted
    assert tu["promptTokens"] == 12000
    assert tu["completionTokens"] == 50
    assert tu["totalTokens"] == 12050
    assert tu["cachedTokens"] == 8000
    assert tu["toolCallCount"] == 0
    assert tu["registeredToolCount"] == 42
    assert tu["llmCallCount"] == 3
    assert tu["subKaniPromptTokens"] == 5000
    assert tu["subKaniCompletionTokens"] == 200
    assert tu["subKaniCallCount"] == 2
    assert tu["estimatedCostUsd"] == 0.042
    assert tu["modelId"] == "openai/gpt-4.1-nano"


async def test_model_selected_persists_on_assistant_message():
    """model_selected event stamps modelId on the assistant message."""
    events = [
        ("message_start", {}),
        ("model_selected", {"modelId": "openai/gpt-5.4"}),
        ("user_message", {"content": "hi", "messageId": "u1"}),
        ("assistant_message", {"content": "hello", "messageId": "a1"}),
        (
            "message_end",
            {"promptTokens": 100, "completionTokens": 10, "totalTokens": 110},
        ),
    ]

    redis = FakeRedis(_make_redis_entries(events))
    messages = await read_stream_messages(redis, "test-stream")

    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].get("modelId") == "openai/gpt-5.4"


async def test_subkani_models_and_token_usage_persist():
    """Sub-kani model identity and token usage persist through round-trip."""
    events = [
        ("message_start", {}),
        ("model_selected", {"modelId": "openai/gpt-4.1"}),
        ("user_message", {"content": "build something", "messageId": "u1"}),
        (
            "subkani_task_start",
            {"task": "Find genes", "modelId": "openai/gpt-4.1-mini"},
        ),
        (
            "subkani_tool_call_start",
            {
                "task": "Find genes",
                "id": "tc1",
                "name": "search_for_searches",
                "arguments": {},
            },
        ),
        ("subkani_tool_call_end", {"task": "Find genes", "id": "tc1", "result": "{}"}),
        (
            "subkani_task_end",
            {
                "task": "Find genes",
                "status": "done",
                "modelId": "openai/gpt-4.1-mini",
                "promptTokens": 3000,
                "completionTokens": 100,
                "llmCallCount": 2,
                "estimatedCostUsd": 0.01,
            },
        ),
        ("assistant_message", {"content": "Done building", "messageId": "a1"}),
        (
            "message_end",
            {"promptTokens": 5000, "completionTokens": 200, "totalTokens": 5200},
        ),
    ]

    redis = FakeRedis(_make_redis_entries(events))
    messages = await read_stream_messages(redis, "test-stream")

    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1

    activity = assistant_msgs[0].get("subKaniActivity")
    assert activity is not None

    # Models persisted
    assert activity.get("models", {}).get("Find genes") == "openai/gpt-4.1-mini"

    # Token usage persisted
    tu = activity.get("tokenUsage", {}).get("Find genes")
    assert tu is not None
    assert tu["promptTokens"] == 3000
    assert tu["completionTokens"] == 100
    assert tu["llmCallCount"] == 2
    assert tu["estimatedCostUsd"] == 0.01


async def test_old_format_message_end_defaults_gracefully():
    """Old message_end events (5 fields only) default new fields to 0/empty."""
    events = [
        ("message_start", {}),
        ("user_message", {"content": "hi", "messageId": "u1"}),
        ("assistant_message", {"content": "hello", "messageId": "a1"}),
        (
            "message_end",
            {
                "promptTokens": 100,
                "completionTokens": 10,
                "totalTokens": 110,
                "toolCallCount": 0,
                "registeredToolCount": 42,
            },
        ),
    ]

    redis = FakeRedis(_make_redis_entries(events))
    messages = await read_stream_messages(redis, "test-stream")

    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    tu = assistant_msgs[0].get("tokenUsage")
    assert tu is not None

    # Old fields present
    assert tu["promptTokens"] == 100
    assert tu["totalTokens"] == 110

    # New fields default to 0/empty
    assert tu["cachedTokens"] == 0
    assert tu["llmCallCount"] == 0
    assert tu["subKaniPromptTokens"] == 0
    assert tu["estimatedCostUsd"] == 0.0
    assert tu["modelId"] == ""
