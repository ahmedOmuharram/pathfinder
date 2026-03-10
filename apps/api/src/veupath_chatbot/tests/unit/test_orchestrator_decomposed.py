"""Tests for decomposed _chat_producer helper functions.

Each extracted function is tested in isolation with mocked dependencies.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from veupath_chatbot.services.chat.orchestrator import (
    _build_agent_context,
    _handle_cancellation,
    _handle_error,
    _run_stream_loop,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _make_projection(**overrides: Any) -> SimpleNamespace:
    defaults = {
        "name": "Test Strategy",
        "plan": {},
        "steps": [],
        "root_step_id": None,
        "record_type": "gene",
        "model_id": "claude-sonnet-4-20250514",
        "wdk_strategy_id": None,
        "is_saved": False,
        "site_id": "plasmodb",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_session_and_repo() -> tuple[AsyncMock, MagicMock]:
    session = AsyncMock()
    repo = MagicMock()
    repo.session = session
    repo.complete_operation = AsyncMock()
    repo.fail_operation = AsyncMock()
    repo.cancel_operation = AsyncMock()
    return session, repo


async def _async_iter(items: list[dict[str, Any]]) -> Any:
    for item in items:
        yield item


# ── _build_agent_context ─────────────────────────────────────────────


class TestBuildAgentContext:
    """Test the agent context builder."""

    @pytest.mark.asyncio
    async def test_returns_agent_and_effective_model(self) -> None:
        projection = _make_projection()
        stream_id = str(uuid4())
        mock_agent = MagicMock()

        mock_create = MagicMock(return_value=mock_agent)
        mock_resolve = MagicMock(return_value="claude-sonnet-4-20250514")

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator._create_agent",
                mock_create,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._resolve_effective_model_id",
                mock_resolve,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._build_chat_history_from_redis",
                AsyncMock(return_value=[]),
            ),
        ):
            agent, effective_model = await _build_agent_context(
                stream_id_str=stream_id,
                site_id="plasmodb",
                user_id=uuid4(),
                model_message="Hello",
                selected_nodes=None,
                provider_override=None,
                model_override=None,
                reasoning_effort=None,
                mentions=None,
                projection=projection,
            )

        assert agent is mock_agent
        assert effective_model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_passes_strategy_graph_to_agent(self) -> None:
        projection = _make_projection(
            name="My Strategy",
            record_type="transcript",
            root_step_id="step_1",
        )
        stream_id = str(uuid4())
        mock_create = MagicMock(return_value=MagicMock())
        mock_resolve = MagicMock(return_value="claude-sonnet-4-20250514")

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator._create_agent",
                mock_create,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._resolve_effective_model_id",
                mock_resolve,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._build_chat_history_from_redis",
                AsyncMock(return_value=[]),
            ),
        ):
            await _build_agent_context(
                stream_id_str=stream_id,
                site_id="plasmodb",
                user_id=uuid4(),
                model_message="Hello",
                selected_nodes=None,
                provider_override=None,
                model_override=None,
                reasoning_effort=None,
                mentions=None,
                projection=projection,
            )

        call_kwargs = mock_create.call_args.kwargs
        graph = call_kwargs["strategy_graph"]
        assert graph["id"] == stream_id
        assert graph["name"] == "My Strategy"
        assert graph["recordType"] == "transcript"
        assert graph["rootStepId"] == "step_1"

    @pytest.mark.asyncio
    async def test_builds_mention_context_when_mentions_provided(self) -> None:
        projection = _make_projection()
        mentions = [{"type": "step", "id": "step_1"}]
        mock_build = AsyncMock(return_value="Step 1 context")

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator._create_agent",
                MagicMock(return_value=MagicMock()),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._resolve_effective_model_id",
                MagicMock(return_value="claude-sonnet-4-20250514"),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._build_chat_history_from_redis",
                AsyncMock(return_value=[]),
            ),
            patch(
                "veupath_chatbot.services.chat.mention_context.build_mention_context",
                mock_build,
            ),
        ):
            await _build_agent_context(
                stream_id_str=str(uuid4()),
                site_id="plasmodb",
                user_id=uuid4(),
                model_message="Hello",
                selected_nodes=None,
                provider_override=None,
                model_override=None,
                reasoning_effort=None,
                mentions=mentions,
                projection=projection,
                stream_repo=MagicMock(),
            )

        mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_mention_context_without_mentions(self) -> None:
        projection = _make_projection()
        mock_create = MagicMock(return_value=MagicMock())

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator._create_agent",
                mock_create,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._resolve_effective_model_id",
                MagicMock(return_value="claude-sonnet-4-20250514"),
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._build_chat_history_from_redis",
                AsyncMock(return_value=[]),
            ),
        ):
            await _build_agent_context(
                stream_id_str=str(uuid4()),
                site_id="plasmodb",
                user_id=uuid4(),
                model_message="Hello",
                selected_nodes=None,
                provider_override=None,
                model_override=None,
                reasoning_effort=None,
                mentions=None,
                projection=projection,
            )

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["mentioned_context"] is None

    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self) -> None:
        projection = _make_projection()

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator._create_agent",
                None,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._resolve_effective_model_id",
                None,
            ),
            pytest.raises(RuntimeError, match="not configured"),
        ):
            await _build_agent_context(
                stream_id_str=str(uuid4()),
                site_id="plasmodb",
                user_id=uuid4(),
                model_message="Hello",
                selected_nodes=None,
                provider_override=None,
                model_override=None,
                reasoning_effort=None,
                mentions=None,
                projection=projection,
            )


# ── _run_stream_loop ─────────────────────────────────────────────────


class TestRunStreamLoop:
    """Test the stream loop runner."""

    @pytest.mark.asyncio
    async def test_emits_message_start_and_stream_events(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        mock_emit = AsyncMock(return_value="1234-0")
        stream_id = str(uuid4())
        operation_id = "op_test123"
        projection = _make_projection(wdk_strategy_id=42)

        stream_events = [
            {"type": "assistant_delta", "data": {"delta": "hello"}},
            {"type": "assistant_message", "data": {"content": "hello world"}},
            {"type": "message_end", "data": {}},
        ]

        with patch(
            "veupath_chatbot.services.chat.orchestrator.emit",
            mock_emit,
        ):
            await _run_stream_loop(
                redis=redis,
                session=session,
                stream_id_str=stream_id,
                operation_id=operation_id,
                site_id="plasmodb",
                projection=projection,
                stream_iter=_async_iter(stream_events),
                stream_repo=repo,
            )

        # message_start + 3 stream events = 4 emit calls
        assert mock_emit.call_count == 4

        # First call should be message_start
        first_call = mock_emit.call_args_list[0]
        assert first_call[0][3] == "message_start"
        strategy_data = first_call[0][4]["strategy"]
        assert strategy_data["wdkStrategyId"] == 42

        # complete_operation should be called
        repo.complete_operation.assert_called_once_with(operation_id)

    @pytest.mark.asyncio
    async def test_skips_non_dict_events(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        mock_emit = AsyncMock(return_value="1234-0")

        async def mixed_stream() -> Any:
            yield {"type": "assistant_delta", "data": {"delta": "hi"}}
            yield "not a dict"  # should be skipped
            yield 42  # should be skipped
            yield {"type": "message_end", "data": {}}

        with patch(
            "veupath_chatbot.services.chat.orchestrator.emit",
            mock_emit,
        ):
            await _run_stream_loop(
                redis=redis,
                session=session,
                stream_id_str="stream_1",
                operation_id="op_1",
                site_id="plasmodb",
                projection=_make_projection(),
                stream_iter=mixed_stream(),
                stream_repo=repo,
            )

        # message_start + 2 valid events = 3 emit calls
        assert mock_emit.call_count == 3

    @pytest.mark.asyncio
    async def test_extracts_event_type_and_data(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        mock_emit = AsyncMock(return_value="1234-0")

        stream_events = [
            {
                "type": "strategy_update",
                "data": {"graphId": "g1", "step": {"stepId": "s1"}},
            },
        ]

        with patch(
            "veupath_chatbot.services.chat.orchestrator.emit",
            mock_emit,
        ):
            await _run_stream_loop(
                redis=redis,
                session=session,
                stream_id_str="stream_1",
                operation_id="op_1",
                site_id="plasmodb",
                projection=_make_projection(),
                stream_iter=_async_iter(stream_events),
                stream_repo=repo,
            )

        # Second call (after message_start) should be strategy_update
        second_call = mock_emit.call_args_list[1]
        assert second_call[0][3] == "strategy_update"
        assert second_call[0][4]["graphId"] == "g1"


# ── _handle_cancellation ─────────────────────────────────────────────


class TestHandleCancellation:
    """Test cancellation handler."""

    @pytest.mark.asyncio
    async def test_emits_message_end_and_cancels_operation(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        mock_emit = AsyncMock(return_value="1234-0")
        stream_id = "stream_1"
        operation_id = "op_cancel"

        with patch(
            "veupath_chatbot.services.chat.orchestrator.emit",
            mock_emit,
        ):
            await _handle_cancellation(
                redis=redis,
                session=session,
                stream_id_str=stream_id,
                operation_id=operation_id,
                stream_repo=repo,
            )

        mock_emit.assert_called_once()
        call_args = mock_emit.call_args[0]
        assert call_args[3] == "message_end"
        assert call_args[4] == {}

        repo.cancel_operation.assert_called_once_with(operation_id)
        session.commit.assert_called_once()


# ── _handle_error ────────────────────────────────────────────────────


class TestHandleError:
    """Test error handler."""

    @pytest.mark.asyncio
    async def test_emits_error_and_message_end(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        mock_emit = AsyncMock(return_value="1234-0")
        error = ValueError("Something broke")

        with patch(
            "veupath_chatbot.services.chat.orchestrator.emit",
            mock_emit,
        ):
            await _handle_error(
                error=error,
                redis=redis,
                session=session,
                stream_id_str="stream_1",
                operation_id="op_err",
                stream_repo=repo,
            )

        assert mock_emit.call_count == 2

        # First call: error event
        error_call = mock_emit.call_args_list[0][0]
        assert error_call[3] == "error"
        assert error_call[4]["error"] == "Something broke"

        # Second call: message_end
        end_call = mock_emit.call_args_list[1][0]
        assert end_call[3] == "message_end"
        assert end_call[4] == {}

        repo.fail_operation.assert_called_once_with("op_err")

    @pytest.mark.asyncio
    async def test_logs_error(self) -> None:
        session, repo = _make_session_and_repo()
        redis = MagicMock()
        error = RuntimeError("kaboom")

        with (
            patch(
                "veupath_chatbot.services.chat.orchestrator.emit",
                AsyncMock(return_value="1234-0"),
            ),
            patch("veupath_chatbot.services.chat.orchestrator.logger") as mock_logger,
        ):
            await _handle_error(
                error=error,
                redis=redis,
                session=session,
                stream_id_str="stream_1",
                operation_id="op_err",
                stream_repo=repo,
            )

        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args
        assert "kaboom" in str(call_kwargs)
