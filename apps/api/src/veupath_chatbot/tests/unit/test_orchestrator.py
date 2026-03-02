"""Unit tests for the chat orchestrator module.

Covers the mock stream provider, mock chat provider detection, and the
start_chat_stream entry point with mocked dependencies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from veupath_chatbot.services.chat.orchestrator import (
    _mock_stream_chat,
    _use_mock_chat_provider,
    start_chat_stream,
)

# ---------------------------------------------------------------------------
# _use_mock_chat_provider
# ---------------------------------------------------------------------------


class TestUseMockChatProvider:
    """Test mock provider detection."""

    def test_returns_true_when_mock(self) -> None:
        mock_settings = MagicMock()
        mock_settings.chat_provider = "mock"
        with patch(
            "veupath_chatbot.platform.config.get_settings",
            return_value=mock_settings,
        ):
            assert _use_mock_chat_provider() is True

    def test_returns_true_case_insensitive(self) -> None:
        mock_settings = MagicMock()
        mock_settings.chat_provider = "  MOCK  "
        with patch(
            "veupath_chatbot.platform.config.get_settings",
            return_value=mock_settings,
        ):
            assert _use_mock_chat_provider() is True

    def test_returns_false_when_default(self) -> None:
        mock_settings = MagicMock()
        mock_settings.chat_provider = "default"
        with patch(
            "veupath_chatbot.platform.config.get_settings",
            return_value=mock_settings,
        ):
            assert _use_mock_chat_provider() is False

    def test_returns_false_when_empty(self) -> None:
        mock_settings = MagicMock()
        mock_settings.chat_provider = ""
        with patch(
            "veupath_chatbot.platform.config.get_settings",
            return_value=mock_settings,
        ):
            assert _use_mock_chat_provider() is False


# ---------------------------------------------------------------------------
# _mock_stream_chat
# ---------------------------------------------------------------------------


class TestMockStreamChat:
    """Test the deterministic mock chat stream generator."""

    @pytest.mark.asyncio
    async def test_basic_message_yields_deltas_and_end(self) -> None:
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="Hello"):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "assistant_delta" in types
        assert "assistant_message" in types
        assert types[-1] == "message_end"

    @pytest.mark.asyncio
    async def test_basic_message_echoes_input(self) -> None:
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="Test input"):
            events.append(ev)

        # The assistant_message should contain the input
        assistant_messages = [e for e in events if e["type"] == "assistant_message"]
        assert len(assistant_messages) == 1
        content = assistant_messages[0]["data"]["content"]
        assert "Test input" in content

    @pytest.mark.asyncio
    async def test_artifact_graph_trigger_yields_planning_artifact(self) -> None:
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="show artifact graph"):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "planning_artifact" in types
        artifact_ev = next(e for e in events if e["type"] == "planning_artifact")
        artifact = artifact_ev["data"]["planningArtifact"]
        assert artifact["id"] == "mock_exec_graph_artifact"
        assert "proposedStrategyPlan" in artifact

    @pytest.mark.asyncio
    async def test_delegation_trigger_yields_subkani_and_strategy_events(self) -> None:
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(
            message="delegate_strategy_subtasks", strategy_id="test-strat-123"
        ):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "subkani_task_start" in types
        assert "subkani_tool_call_start" in types
        assert "subkani_tool_call_end" in types
        assert "subkani_task_end" in types
        assert "strategy_update" in types
        assert "assistant_message" in types
        assert types[-1] == "message_end"

        # strategy_update should use the provided strategy_id
        su_events = [e for e in events if e["type"] == "strategy_update"]
        assert len(su_events) >= 1
        assert su_events[0]["data"]["graphId"] == "test-strat-123"

    @pytest.mark.asyncio
    async def test_delegation_keyword_in_message(self) -> None:
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="run delegation now"):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "subkani_task_start" in types

    @pytest.mark.asyncio
    async def test_slow_message_still_completes(self) -> None:
        """Messages with 'slow' keyword add delays but should still complete."""
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="slow test"):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "message_end" in types

    @pytest.mark.asyncio
    async def test_delegation_default_strategy_id(self) -> None:
        """When no strategy_id is given, uses default 'mock_graph_delegation'."""
        events: list[dict[str, Any]] = []
        async for ev in _mock_stream_chat(message="delegation test"):
            events.append(ev)

        su_events = [e for e in events if e["type"] == "strategy_update"]
        assert su_events[0]["data"]["graphId"] == "mock_graph_delegation"


# ---------------------------------------------------------------------------
# start_chat_stream
# ---------------------------------------------------------------------------


def _make_fake_strategy(
    strategy_id: UUID | None = None,
    model_id: str | None = None,
) -> SimpleNamespace:
    sid = strategy_id or uuid4()
    return SimpleNamespace(
        id=sid,
        name="Draft Strategy",
        title="Draft Strategy",
        site_id="plasmodb",
        record_type=None,
        wdk_strategy_id=None,
        plan={},
        steps=[],
        root_step_id=None,
        model_id=model_id,
        messages=[],
        created_at=None,
        updated_at=None,
    )


class TestStartChatStream:
    """Test the start_chat_stream orchestrator entry point."""

    @pytest.mark.asyncio
    async def test_start_chat_stream_returns_async_iterator(self) -> None:
        """start_chat_stream should return an async iterator of SSE strings."""
        strategy = _make_fake_strategy()
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
        ):
            result = await start_chat_stream(
                message="Hello",
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
            )

            # Collect all yielded SSE strings
            events: list[str] = []
            async for sse_line in result:
                events.append(sse_line)

            # Should yield at least a start event
            assert len(events) > 0
            # First event should be the message_start
            assert "message_start" in events[0]

    @pytest.mark.asyncio
    async def test_start_chat_stream_persists_model_id_on_change(self) -> None:
        """When effective_model differs from strategy.model_id, it should be persisted."""
        strategy = _make_fake_strategy(model_id="openai/gpt-4o")
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",  # different from strategy.model_id
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
        ):
            result = await start_chat_stream(
                message="Hello",
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
            )

            # Consume the iterator to trigger side effects
            async for _ in result:
                pass

            # Should have called update to persist the new model_id
            strategy_repo.update.assert_called_once_with(
                strategy.id, model_id="openai/gpt-5", model_id_set=True
            )

    @pytest.mark.asyncio
    async def test_start_chat_stream_skips_model_persist_when_unchanged(self) -> None:
        """When effective_model matches strategy.model_id, no update is needed."""
        strategy = _make_fake_strategy(model_id="openai/gpt-5")
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",  # same as strategy.model_id
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
        ):
            result = await start_chat_stream(
                message="Hello",
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
            )

            # Consume the iterator
            async for _ in result:
                pass

            # Should NOT have called update since model_id unchanged
            strategy_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_chat_stream_with_mentions(self) -> None:
        """When mentions are provided, build_mention_context should be called."""
        strategy = _make_fake_strategy()
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        mock_build_mention = AsyncMock(return_value="Context about strategy X")

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ) as mock_create_agent,
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
            patch(
                "veupath_chatbot.services.chat.mention_context.build_mention_context",
                mock_build_mention,
            ),
        ):
            result = await start_chat_stream(
                message="Hello",
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
                mentions=[{"type": "strategy", "id": "abc123"}],
            )

            # Consume the iterator
            async for _ in result:
                pass

            mock_build_mention.assert_called_once()
            # create_agent should receive mentioned_context
            call_kwargs = mock_create_agent.call_args
            assert (
                call_kwargs.kwargs.get("mentioned_context")
                == "Context about strategy X"
            )

    @pytest.mark.asyncio
    async def test_start_chat_stream_selected_nodes_parsed(self) -> None:
        """Messages with __NODE__ prefix should have nodes parsed out."""
        strategy = _make_fake_strategy()
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ) as mock_create_agent,
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
        ):
            result = await start_chat_stream(
                message='__NODE__{"stepId":"s1"}\nModify this step',
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
            )

            # Consume
            async for _ in result:
                pass

            # create_agent should receive selected_nodes
            call_kwargs = mock_create_agent.call_args
            assert call_kwargs.kwargs.get("selected_nodes") == {"stepId": "s1"}

    @pytest.mark.asyncio
    async def test_start_chat_stream_calls_get_or_create_user(self) -> None:
        """The orchestrator should ensure the user exists."""
        strategy = _make_fake_strategy()
        user_id = uuid4()

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=None)

        strategy_repo = MagicMock()
        strategy_repo.add_message = AsyncMock()
        strategy_repo.clear_thinking = AsyncMock()
        strategy_repo.update = AsyncMock(return_value=strategy)
        strategy_repo.refresh = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.ensure_strategy",
                new=AsyncMock(return_value=strategy),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.append_user_message",
                new=AsyncMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_chat_history",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.build_strategy_payload",
                return_value={"id": str(strategy.id)},
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.resolve_effective_model_id",
                return_value="openai/gpt-5",
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator.create_agent",
                return_value=MagicMock(),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._use_mock_chat_provider",
                return_value=True,
            ),
        ):
            await start_chat_stream(
                message="Hello",
                site_id="plasmodb",
                strategy_id=None,
                user_id=user_id,
                user_repo=user_repo,
                strategy_repo=strategy_repo,
            )

            # Just getting the iterator triggers pre-stream setup
            user_repo.get_or_create.assert_called_once_with(user_id)
