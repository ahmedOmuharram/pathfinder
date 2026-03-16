"""Test that stream_chat emits enhanced message_end with all new fields."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from kani.engines.base import Completion
from kani.models import ChatMessage, ChatRole

from veupath_chatbot.services.chat.streaming import stream_chat


async def _collect_events(agent, message, model_id="openai/gpt-4.1"):
    """Run stream_chat and collect all emitted events."""
    events = []
    async for event in stream_chat(agent, message, model_id=model_id):
        events.append(event)
    return events


def _make_mock_agent():
    """Create a mock Kani agent that yields one assistant message.

    The key issue: ``agent.full_round_stream(message)`` must be an async
    generator, and each yielded ``stream`` must itself be an async iterable
    of tokens with ``.role``, ``.message()``, and ``.completion()`` methods.
    """
    msg = ChatMessage.assistant("Hello!")
    msg.extra = {}
    completion = Completion(message=msg, prompt_tokens=100, completion_tokens=20)

    # Build the stream mock — async iterable of tokens
    stream = MagicMock()
    stream.role = ChatRole.ASSISTANT

    # Make the stream an async iterable that yields tokens
    async def _token_iter():
        yield "Hello"
        yield "!"

    stream.__aiter__ = lambda self: _token_iter()

    # message() and completion() are coroutines
    stream.message = AsyncMock(return_value=msg)
    stream.completion = AsyncMock(return_value=completion)

    # Build the agent mock
    agent = MagicMock()
    agent.functions = {}

    # full_round_stream must be an async generator — NOT an AsyncMock
    async def _mock_full_round_stream(message):
        yield stream

    agent.full_round_stream = _mock_full_round_stream

    return agent


def test_message_end_has_all_new_fields():
    events = asyncio.run(_collect_events(_make_mock_agent(), "hi"))
    message_end = [e for e in events if e.get("type") == "message_end"]
    assert len(message_end) == 1
    data = message_end[0]["data"]

    # Original fields
    assert "promptTokens" in data
    assert "completionTokens" in data
    assert "totalTokens" in data
    assert "toolCallCount" in data
    assert "registeredToolCount" in data

    # New fields
    assert "cachedTokens" in data
    assert "llmCallCount" in data
    assert "subKaniPromptTokens" in data
    assert "subKaniCompletionTokens" in data
    assert "subKaniCallCount" in data
    assert "estimatedCostUsd" in data
    assert "modelId" in data

    # Verify values
    assert data["llmCallCount"] == 1  # one assistant stream
    assert data["modelId"] == "openai/gpt-4.1"
    assert isinstance(data["estimatedCostUsd"], float)
    assert data["promptTokens"] == 100
    assert data["completionTokens"] == 20
