"""Integration-style tests for the message persistence chain.

Verifies the FULL path a user experiences on refresh:
  emit(user_message) → emit(assistant_message) → read_stream_messages() →
  build_projection_response() → messages returned in StrategyResponse

Uses fakeredis (real Redis protocol, in-memory) so we test actual XADD/XRANGE
behavior.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest

from veupath_chatbot.platform.events import (
    emit,
    read_stream_messages,
    read_stream_thinking,
)
from veupath_chatbot.services.chat.orchestrator import start_chat_stream
from veupath_chatbot.services.chat.types import ChatContext
from veupath_chatbot.transport.http.routers.strategies._shared import (
    build_projection_response,
)


@pytest.fixture
def redis():
    """A fresh fakeredis instance per test."""
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def stream_id() -> str:
    return str(uuid4())


@pytest.fixture
def operation_id() -> str:
    return f"op_{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Core emit → read round-trip
# ---------------------------------------------------------------------------


class TestEmitAndRead:
    """Test that events emitted to Redis are readable."""

    @pytest.mark.asyncio
    async def test_user_message_persists_in_redis(self, redis, stream_id, operation_id):
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Hello world", "messageId": "msg-1"},
        )

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello world"
        assert messages[0]["messageId"] == "msg-1"

    @pytest.mark.asyncio
    async def test_assistant_message_persists_in_redis(
        self, redis, stream_id, operation_id
    ):
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "I can help with that.", "messageId": "msg-2"},
        )

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == "I can help with that."

    @pytest.mark.asyncio
    async def test_full_conversation_round_trip(self, redis, stream_id, operation_id):
        """Simulate: user sends → assistant responds → user sends again → read all."""
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "What is malaria?", "messageId": "msg-1"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Malaria is a disease caused by Plasmodium parasites.",
                "messageId": "msg-2",
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "How is it transmitted?", "messageId": "msg-3"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "Through infected mosquito bites.", "messageId": "msg-4"},
        )

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is malaria?"
        assert messages[1]["role"] == "assistant"
        assert (
            messages[1]["content"]
            == "Malaria is a disease caused by Plasmodium parasites."
        )
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "How is it transmitted?"
        assert messages[3]["role"] == "assistant"
        assert messages[3]["content"] == "Through infected mosquito bites."
        # All messages should include a timestamp derived from the Redis entry ID.
        for msg in messages:
            assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_non_message_events_are_filtered_from_message_list(
        self, redis, stream_id, operation_id
    ):
        """strategy_update etc. should NOT appear as separate messages, but tool
        calls SHOULD be aggregated into the assistant message."""
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Hi", "messageId": "m1"},
        )
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_start",
            {"id": "tc1", "name": "search"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_end",
            {"id": "tc1", "result": "found it"},
        )
        await emit(
            redis, stream_id, operation_id, "strategy_update", {"graphId": "abc"}
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "Done.", "messageId": "m2"},
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 2
        assert messages[0]["content"] == "Hi"
        assert messages[1]["content"] == "Done."
        # Tool call should be aggregated INTO the assistant message.
        assert messages[1]["toolCalls"] is not None
        assert len(messages[1]["toolCalls"]) == 1
        assert messages[1]["toolCalls"][0]["id"] == "tc1"
        assert messages[1]["toolCalls"][0]["result"] == "found it"

    @pytest.mark.asyncio
    async def test_assistant_message_preserves_extra_fields_on_event(
        self, redis, stream_id, operation_id
    ):
        """Fields directly on assistant_message event data should survive."""
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Found it.",
                "messageId": "msg-5",
                "citations": [{"source": "PlasmoDB"}],
                "toolCalls": [{"id": "tc1", "name": "search"}],
                "reasoning": "I searched for the gene.",
            },
        )

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        msg = messages[0]
        assert msg["citations"] == [{"source": "PlasmoDB"}]
        assert msg["toolCalls"] == [{"id": "tc1", "name": "search"}]
        assert msg["reasoning"] == "I searched for the gene."

    @pytest.mark.asyncio
    async def test_tool_calls_aggregated_into_assistant_message(
        self, redis, stream_id, operation_id
    ):
        """Tool calls from separate events should be aggregated onto the assistant message."""
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_start",
            {
                "id": "tc1",
                "name": "search_genes",
                "arguments": {"query": "PfEMP1"},
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_end",
            {
                "id": "tc1",
                "result": '{"genes": ["PF3D7_0100100"]}',
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_start",
            {
                "id": "tc2",
                "name": "get_gene_info",
                "arguments": {"id": "PF3D7_0100100"},
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_end",
            {
                "id": "tc2",
                "result": '{"name": "VAR", "product": "erythrocyte membrane"}',
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Found PfEMP1.",
                "messageId": "m1",
            },
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        msg = messages[0]
        assert len(msg["toolCalls"]) == 2
        assert msg["toolCalls"][0]["name"] == "search_genes"
        assert msg["toolCalls"][0]["result"] == '{"genes": ["PF3D7_0100100"]}'
        assert msg["toolCalls"][1]["name"] == "get_gene_info"

    @pytest.mark.asyncio
    async def test_citations_aggregated_into_assistant_message(
        self, redis, stream_id, operation_id
    ):
        """Citations from separate events should be aggregated onto the assistant message."""
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "citations",
            {
                "citations": [
                    {"id": "c1", "title": "Paper 1", "url": "https://example.com/1"},
                    {"id": "c2", "title": "Paper 2", "url": "https://example.com/2"},
                ],
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Based on the literature...",
                "messageId": "m1",
            },
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert len(messages[0]["citations"]) == 2
        assert messages[0]["citations"][0]["title"] == "Paper 1"

    @pytest.mark.asyncio
    async def test_reasoning_aggregated_into_assistant_message(
        self, redis, stream_id, operation_id
    ):
        """Reasoning from a separate event should be attached to the assistant message."""
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "reasoning",
            {
                "reasoning": "I need to search for genes related to PfEMP1 first.",
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Here are the results.",
                "messageId": "m1",
            },
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert (
            messages[0]["reasoning"]
            == "I need to search for genes related to PfEMP1 first."
        )

    @pytest.mark.asyncio
    async def test_planning_artifacts_aggregated(self, redis, stream_id, operation_id):
        """Planning artifacts from separate events should be aggregated."""
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "planning_artifact",
            {
                "planningArtifact": {
                    "id": "pa1",
                    "title": "Search plan",
                    "summaryMarkdown": "...",
                },
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "I've created a plan.",
                "messageId": "m1",
            },
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert len(messages[0]["planningArtifacts"]) == 1
        assert messages[0]["planningArtifacts"][0]["id"] == "pa1"

    @pytest.mark.asyncio
    async def test_subkani_activity_aggregated(self, redis, stream_id, operation_id):
        """Sub-kani activity from separate events should be aggregated."""
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "subkani_task_start",
            {"task": "build-strategy"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "subkani_tool_call_start",
            {
                "task": "build-strategy",
                "id": "stc1",
                "name": "search_for_searches",
                "arguments": {"query": "gene"},
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "subkani_tool_call_end",
            {
                "task": "build-strategy",
                "id": "stc1",
                "result": "found searches",
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "subkani_task_end",
            {
                "task": "build-strategy",
                "status": "done",
            },
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {
                "content": "Strategy built.",
                "messageId": "m1",
            },
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        activity = messages[0]["subKaniActivity"]
        assert activity is not None
        assert "build-strategy" in activity["calls"]
        assert len(activity["calls"]["build-strategy"]) == 1
        assert activity["calls"]["build-strategy"][0]["id"] == "stc1"
        assert activity["calls"]["build-strategy"][0]["result"] == "found searches"
        assert activity["status"]["build-strategy"] == "done"

    @pytest.mark.asyncio
    async def test_turn_accumulators_reset_between_turns(
        self, redis, stream_id, operation_id
    ):
        """Metadata from turn 1 should NOT leak into turn 2."""
        # Turn 1: has tool calls
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Q1", "messageId": "u1"},
        )
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_start",
            {"id": "tc1", "name": "search"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_end",
            {"id": "tc1", "result": "ok"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "reasoning",
            {"reasoning": "Turn 1 reasoning"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "A1", "messageId": "a1"},
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        # Turn 2: no tool calls, no reasoning
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Q2", "messageId": "u2"},
        )
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "A2", "messageId": "a2"},
        )
        await emit(redis, stream_id, operation_id, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 4
        # Turn 1 assistant should have tool calls and reasoning
        assert "toolCalls" in messages[1]
        assert messages[1]["reasoning"] == "Turn 1 reasoning"
        # Turn 2 assistant should NOT have tool calls or reasoning from turn 1
        assert "toolCalls" not in messages[3]
        assert "reasoning" not in messages[3]

    @pytest.mark.asyncio
    async def test_empty_stream_returns_empty_list(self, redis, stream_id):
        messages = await read_stream_messages(redis, stream_id)
        assert messages == []

    @pytest.mark.asyncio
    async def test_multiple_operations_on_same_stream(self, redis, stream_id):
        """Two chat operations on the same stream — all messages should appear."""
        op1 = "op_first"
        op2 = "op_second"
        await emit(
            redis,
            stream_id,
            op1,
            "user_message",
            {"content": "First question", "messageId": "m1"},
        )
        await emit(
            redis,
            stream_id,
            op1,
            "assistant_message",
            {"content": "First answer", "messageId": "m2"},
        )
        await emit(
            redis,
            stream_id,
            op2,
            "user_message",
            {"content": "Second question", "messageId": "m3"},
        )
        await emit(
            redis,
            stream_id,
            op2,
            "assistant_message",
            {"content": "Second answer", "messageId": "m4"},
        )

        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 4
        assert [m["content"] for m in messages] == [
            "First question",
            "First answer",
            "Second question",
            "Second answer",
        ]


# ---------------------------------------------------------------------------
# build_projection_response (the GET /strategies/{id} response builder)
# ---------------------------------------------------------------------------


@dataclass
class _FakeStream:
    id: UUID
    site_id: str = "plasmodb"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class _FakeProjection:
    """Duck-typed StreamProjection for tests — avoids SQLAlchemy instrumentation."""

    stream_id: UUID
    stream: _FakeStream
    name: str = "Test Conv"
    record_type: str | None = None
    wdk_strategy_id: int | None = None
    gene_set_id: str | None = None
    is_saved: bool = False
    model_id: str | None = None
    message_count: int = 0
    step_count: int = 0
    plan: dict[str, Any] = field(default_factory=dict)
    steps: list[Any] = field(default_factory=list)
    root_step_id: str | None = None
    estimated_size: int | None = None
    last_event_id: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    dismissed_at: datetime | None = None

    @property
    def site_id(self) -> str:
        return self.stream.site_id if self.stream else ""


def _make_projection(stream_id: str, name: str = "Test Conv") -> Any:
    """Build a duck-typed StreamProjection with the minimum fields needed."""
    sid = UUID(stream_id) if isinstance(stream_id, str) else stream_id
    return _FakeProjection(stream_id=sid, stream=_FakeStream(id=sid), name=name)


class TestBuildProjectionResponse:
    """Test that the response builder correctly includes Redis messages."""

    @pytest.mark.asyncio
    async def test_response_includes_messages_from_redis(
        self, redis, stream_id, operation_id
    ):
        """This is THE test for the refresh bug. Emit → read → build response → check messages."""
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Hello", "messageId": "m1"},
        )
        await emit(
            redis,
            stream_id,
            operation_id,
            "assistant_message",
            {"content": "Hi there!", "messageId": "m2"},
        )

        messages = await read_stream_messages(redis, stream_id)
        proj = _make_projection(stream_id)
        response = build_projection_response(proj, messages=messages)

        assert response.messages is not None, (
            "messages should NOT be None after a conversation"
        )
        assert len(response.messages) == 2
        assert response.messages[0].role == "user"
        assert response.messages[0].content == "Hello"
        assert response.messages[1].role == "assistant"
        assert response.messages[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_response_with_no_messages(self, stream_id):
        proj = _make_projection(stream_id)
        response = build_projection_response(proj, messages=None)

        assert response.messages is None

    @pytest.mark.asyncio
    async def test_response_with_empty_messages(self, stream_id):
        proj = _make_projection(stream_id)
        response = build_projection_response(proj, messages=[])

        assert response.messages is None  # empty list → None (no messages to show)

    @pytest.mark.asyncio
    async def test_response_includes_thinking(self, redis, stream_id, operation_id):
        await emit(redis, stream_id, operation_id, "message_start", {})
        await emit(
            redis,
            stream_id,
            operation_id,
            "tool_call_start",
            {"id": "tc1", "name": "search_genes", "arguments": {"query": "PfEMP1"}},
        )

        thinking = await read_stream_thinking(redis, stream_id)
        proj = _make_projection(stream_id)
        response = build_projection_response(proj, thinking=thinking)

        assert response.thinking is not None
        assert len(response.thinking.tool_calls) == 1


# ---------------------------------------------------------------------------
# Full orchestrator chain: start_chat_stream → emit → GET readable
# ---------------------------------------------------------------------------


class TestOrchestratorEmitsReadableMessages:
    """Test that start_chat_stream emits a user_message that survives refresh."""

    @pytest.mark.asyncio
    async def test_orchestrator_user_message_readable_after_emit(
        self, redis, operation_id
    ):
        """After start_chat_stream emits user_message, read_stream_messages should find it."""
        stream_id = str(uuid4())

        # Simulate what start_chat_stream does: emit user_message.
        await emit(
            redis,
            stream_id,
            operation_id,
            "user_message",
            {"content": "Find genes related to PfEMP1", "messageId": str(uuid4())},
        )

        # Simulate what GET /strategies/{id} does: read from Redis.
        messages = await read_stream_messages(redis, stream_id)

        assert len(messages) == 1
        assert messages[0]["content"] == "Find genes related to PfEMP1"
        assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_start_chat_stream_uses_correct_stream_key(self, redis):
        """The orchestrator must emit to stream:{stream.id}, and the read must use the same key."""
        stream_uuid = uuid4()
        fake_stream = SimpleNamespace(id=stream_uuid)

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()

        stream_repo = MagicMock()
        stream_repo.get_by_id = AsyncMock(return_value=fake_stream)
        stream_repo.create = AsyncMock(return_value=fake_stream)
        stream_repo.register_operation = AsyncMock()
        stream_repo.session = mock_session

        context = ChatContext(
            user_id=uuid4(),
            user_repo=user_repo,
            stream_repo=stream_repo,
        )

        def _fake_create_task(coro: Any) -> MagicMock:
            coro.close()
            task = MagicMock()
            task.add_done_callback = MagicMock()
            return task

        # Use REAL redis (fakeredis) for emit — don't mock it away.
        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.get_redis",
                return_value=redis,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.asyncio.create_task",
                side_effect=_fake_create_task,
            ),
        ):
            _op_id, returned_stream_id = await start_chat_stream(
                message="Test message for persistence",
                site_id="plasmodb",
                strategy_id=stream_uuid,
                context=context,
            )

        # NOW: read from Redis using the SAME stream_id the endpoint would use.
        messages = await read_stream_messages(redis, returned_stream_id)

        assert len(messages) == 1, (
            f"Expected 1 message in Redis stream:{returned_stream_id}, got {len(messages)}. "
            "This means the user_message emitted by start_chat_stream is NOT readable "
            "by the GET endpoint — messages WILL disappear on refresh."
        )
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test message for persistence"
