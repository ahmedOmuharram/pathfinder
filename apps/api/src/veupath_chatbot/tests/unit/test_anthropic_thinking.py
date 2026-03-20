"""Tests for Anthropic thinking block handling.

Covers:
1. CachedAnthropicEngine._translate_anthropic_message wraps bare MessageParts
2. _extract_reasoning extracts thinking content from message parts
3. stream_chat emits reasoning SSE events for thinking blocks
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from anthropic.types import Message, TextBlock, ThinkingBlock, Usage
from kani.engines.anthropic.parts import AnthropicThinkingPart
from kani.engines.base import Completion
from kani.models import ChatMessage, ChatRole
from kani.parts.reasoning import ReasoningPart

from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine
from veupath_chatbot.services.chat.streaming import _extract_reasoning, stream_chat

# ---------------------------------------------------------------------------
# Helpers: build realistic Anthropic API Message objects
# ---------------------------------------------------------------------------


def _make_anthropic_message(
    content_blocks: list,
    input_tokens: int = 50,
    output_tokens: int = 100,
) -> Message:
    """Build a real ``anthropic.types.Message`` with the given content blocks."""
    return Message(
        id="msg_test123",
        content=content_blocks,
        model="claude-sonnet-4-5-20250929",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


# ---------------------------------------------------------------------------
# CachedAnthropicEngine._translate_anthropic_message
# ---------------------------------------------------------------------------


class TestTranslateAnthropicMessage:
    """Verify the kani bug fix: bare MessagePart content gets wrapped in a list."""

    def _make_engine(self) -> CachedAnthropicEngine:
        """Build an engine without hitting the real API."""
        engine = CachedAnthropicEngine.__new__(CachedAnthropicEngine)
        engine.model = "claude-sonnet-4-5-20250929"
        engine.max_tokens = 8192
        engine.hyperparams = {}
        # TokenCached mixin attributes (normally set in __init__)
        engine._message_token_cache = {}
        engine._prompt_token_cache = {}
        return engine

    def test_thinking_only_response_does_not_crash(self):
        """A response with only a thinking block should not raise ValidationError.

        This is the exact scenario from the bug report: Anthropic returns a
        thinking block with no text, kani sets ``content = parts[0]`` (a bare
        AnthropicThinkingPart), and Pydantic rejects it.
        """
        engine = self._make_engine()
        message = _make_anthropic_message(
            [
                ThinkingBlock(
                    type="thinking",
                    thinking="Let me analyze this step by step...",
                    signature="sig_abc123",
                ),
            ]
        )

        completion = engine._translate_anthropic_message(message)

        assert isinstance(completion, Completion)
        msg = completion.message
        assert msg.role == ChatRole.ASSISTANT
        # Content must be a list, not a bare MessagePart
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], AnthropicThinkingPart)
        assert msg.content[0].content == "Let me analyze this step by step..."
        assert msg.content[0].signature == "sig_abc123"

    def test_thinking_plus_text_response(self):
        """A response with thinking + text should have both parts in a list."""
        engine = self._make_engine()
        message = _make_anthropic_message(
            [
                ThinkingBlock(
                    type="thinking",
                    thinking="I need to think about this...",
                    signature="sig_def456",
                ),
                TextBlock(type="text", text="Here is my answer."),
            ]
        )

        completion = engine._translate_anthropic_message(message)
        msg = completion.message

        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert isinstance(msg.content[0], AnthropicThinkingPart)
        assert isinstance(msg.content[1], str)
        assert msg.content[1] == "Here is my answer."

    def test_text_only_response_unchanged(self):
        """A plain text response should pass through as a string."""
        engine = self._make_engine()
        message = _make_anthropic_message(
            [
                TextBlock(type="text", text="Simple response."),
            ]
        )

        completion = engine._translate_anthropic_message(message)
        msg = completion.message

        # Single string part stays as string (kani's default behavior)
        assert msg.content == "Simple response."

    def test_token_counts_preserved(self):
        """Prompt and completion token counts survive the wrapping fix."""
        engine = self._make_engine()
        message = _make_anthropic_message(
            [ThinkingBlock(type="thinking", thinking="...", signature="sig")],
            input_tokens=200,
            output_tokens=50,
        )

        completion = engine._translate_anthropic_message(message)

        assert completion.prompt_tokens == 200
        assert completion.completion_tokens == 50


# ---------------------------------------------------------------------------
# _extract_reasoning
# ---------------------------------------------------------------------------


class TestExtractReasoning:
    """Verify reasoning content is extracted from message parts."""

    def test_extracts_anthropic_thinking(self):
        """AnthropicThinkingPart content is extracted."""
        msg = ChatMessage.assistant(
            [
                AnthropicThinkingPart(content="Step 1: analyze", signature="sig1"),
                "Here is the answer.",
            ]
        )
        result = _extract_reasoning(msg)
        assert result == "Step 1: analyze"

    def test_extracts_generic_reasoning_part(self):
        """Plain ReasoningPart content is extracted."""
        msg = ChatMessage.assistant(
            [
                ReasoningPart(content="Deep thought process..."),
                "Final answer.",
            ]
        )
        result = _extract_reasoning(msg)
        assert result == "Deep thought process..."

    def test_multiple_thinking_blocks_joined(self):
        """Multiple thinking parts are joined with double newlines."""
        msg = ChatMessage.assistant(
            [
                AnthropicThinkingPart(content="First thought", signature="sig1"),
                "Intermediate text",
                AnthropicThinkingPart(content="Second thought", signature="sig2"),
            ]
        )
        result = _extract_reasoning(msg)
        assert result == "First thought\n\nSecond thought"

    def test_no_reasoning_returns_none(self):
        """A message with no reasoning parts returns None."""
        msg = ChatMessage.assistant("Plain response.")
        result = _extract_reasoning(msg)
        assert result is None

    def test_empty_reasoning_content_returns_none(self):
        """A thinking block with empty content is skipped."""
        msg = ChatMessage.assistant(
            [
                AnthropicThinkingPart(content="", signature="sig"),
                "Answer.",
            ]
        )
        result = _extract_reasoning(msg)
        assert result is None

    def test_non_message_object_returns_none(self):
        """Gracefully handles objects without parts attribute."""
        result = _extract_reasoning("just a string")
        assert result is None


# ---------------------------------------------------------------------------
# stream_chat reasoning event emission
# ---------------------------------------------------------------------------


def _make_mock_agent_with_thinking(thinking_text: str, response_text: str):
    """Create a mock agent whose response includes thinking + text parts."""
    msg = ChatMessage.assistant(
        [
            AnthropicThinkingPart(content=thinking_text, signature="sig_test"),
            response_text,
        ]
    )
    msg.extra = {}
    completion = Completion(message=msg, prompt_tokens=100, completion_tokens=50)

    stream = MagicMock()
    stream.role = ChatRole.ASSISTANT

    # Streaming tokens only yield the text part (thinking is hidden by __str__)
    async def _token_iter():
        yield response_text

    stream.__aiter__ = lambda self: _token_iter()
    stream.message = AsyncMock(return_value=msg)
    stream.completion = AsyncMock(return_value=completion)

    agent = MagicMock()
    agent.functions = {}

    async def _mock_full_round_stream(message):
        yield stream

    agent.full_round_stream = _mock_full_round_stream
    return agent


def _make_mock_agent_thinking_only(thinking_text: str):
    """Create a mock agent whose response is only a thinking block (no text)."""
    msg = ChatMessage.assistant(
        [
            AnthropicThinkingPart(content=thinking_text, signature="sig_only"),
        ]
    )
    msg.extra = {}
    completion = Completion(message=msg, prompt_tokens=100, completion_tokens=50)

    stream = MagicMock()
    stream.role = ChatRole.ASSISTANT

    # No text tokens to stream
    async def _token_iter():
        return
        yield  # makes it an async generator

    stream.__aiter__ = lambda self: _token_iter()
    stream.message = AsyncMock(return_value=msg)
    stream.completion = AsyncMock(return_value=completion)

    agent = MagicMock()
    agent.functions = {}

    async def _mock_full_round_stream(message):
        yield stream

    agent.full_round_stream = _mock_full_round_stream
    return agent


def _make_mock_agent_no_thinking(response_text: str):
    """Create a mock agent with a plain text response (no thinking)."""
    msg = ChatMessage.assistant(response_text)
    msg.extra = {}
    completion = Completion(message=msg, prompt_tokens=100, completion_tokens=50)

    stream = MagicMock()
    stream.role = ChatRole.ASSISTANT

    async def _token_iter():
        yield response_text

    stream.__aiter__ = lambda self: _token_iter()
    stream.message = AsyncMock(return_value=msg)
    stream.completion = AsyncMock(return_value=completion)

    agent = MagicMock()
    agent.functions = {}

    async def _mock_full_round_stream(message):
        yield stream

    agent.full_round_stream = _mock_full_round_stream
    return agent


async def _collect_events(agent, message="hi", model_id="anthropic/claude-sonnet-4-5"):
    return [event async for event in stream_chat(agent, message, model_id=model_id)]


class TestStreamChatReasoning:
    """Verify stream_chat emits reasoning SSE events for thinking blocks."""

    def test_emits_reasoning_event_for_thinking(self):
        agent = _make_mock_agent_with_thinking(
            "Let me analyze the gene expression patterns...",
            "Based on my analysis, the gene is upregulated.",
        )
        events = asyncio.run(_collect_events(agent))

        reasoning_events = [e for e in events if e.get("type") == "reasoning"]
        assert len(reasoning_events) == 1
        assert reasoning_events[0]["data"]["reasoning"] == (
            "Let me analyze the gene expression patterns..."
        )

    def test_reasoning_event_before_assistant_message(self):
        """Reasoning event should appear before the assistant_message event."""
        agent = _make_mock_agent_with_thinking("Thinking...", "Answer.")
        events = asyncio.run(_collect_events(agent))

        types = [e["type"] for e in events]
        reasoning_idx = types.index("reasoning")
        message_idx = types.index("assistant_message")
        assert reasoning_idx < message_idx

    def test_no_reasoning_event_without_thinking(self):
        """No reasoning event is emitted for plain text responses."""
        agent = _make_mock_agent_no_thinking("Simple answer.")
        events = asyncio.run(_collect_events(agent))

        reasoning_events = [e for e in events if e.get("type") == "reasoning"]
        assert len(reasoning_events) == 0

    def test_thinking_only_still_emits_reasoning(self):
        """A response with only thinking (no text) still emits a reasoning event."""
        agent = _make_mock_agent_thinking_only("Deep internal reasoning...")
        events = asyncio.run(_collect_events(agent))

        reasoning_events = [e for e in events if e.get("type") == "reasoning"]
        assert len(reasoning_events) == 1
        assert reasoning_events[0]["data"]["reasoning"] == "Deep internal reasoning..."

    def test_assistant_message_still_emitted(self):
        """Even with thinking blocks, an assistant_message event is always emitted."""
        agent = _make_mock_agent_with_thinking("Thinking...", "The answer is 42.")
        events = asyncio.run(_collect_events(agent))

        assistant_msgs = [e for e in events if e.get("type") == "assistant_message"]
        assert len(assistant_msgs) == 1

    def test_message_end_still_emitted(self):
        """message_end event is always emitted as the final event."""
        agent = _make_mock_agent_with_thinking("Thinking...", "Answer.")
        events = asyncio.run(_collect_events(agent))

        assert events[-1]["type"] == "message_end"
