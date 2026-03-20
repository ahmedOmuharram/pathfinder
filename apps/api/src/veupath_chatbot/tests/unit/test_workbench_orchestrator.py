"""Unit tests for workbench chat orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from veupath_chatbot.services.workbench_chat import orchestrator


class TestStartWorkbenchChatStream:
    @pytest.mark.asyncio
    async def test_returns_operation_and_stream_ids(self) -> None:
        mock_create_agent = MagicMock()
        mock_resolve_model = MagicMock(return_value="openai/gpt-4.1-nano")
        orchestrator.configure(
            create_workbench_agent_fn=mock_create_agent,
            resolve_model_id_fn=mock_resolve_model,
        )

        user_id = uuid4()
        stream_id = uuid4()
        mock_user_repo = AsyncMock()
        mock_user_repo.get_or_create = AsyncMock(return_value=MagicMock(id=user_id))
        mock_stream_repo = AsyncMock()
        mock_stream_repo.find_by_experiment = AsyncMock(return_value=None)
        mock_stream_repo.create = AsyncMock(return_value=MagicMock(id=stream_id))
        mock_stream_repo.register_operation = AsyncMock()
        mock_stream_repo.session = AsyncMock()
        mock_stream_repo.session.commit = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.workbench_chat.orchestrator.emit",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.workbench_chat.orchestrator.get_redis",
            ),
        ):
            op_id, result_stream_id = await orchestrator.start_workbench_chat_stream(
                message="Interpret these results",
                site_id="plasmodb",
                experiment_id="exp-1",
                user_id=user_id,
                user_repo=mock_user_repo,
                stream_repo=mock_stream_repo,
            )

        assert op_id.startswith("op_")
        assert result_stream_id == str(stream_id)
        mock_stream_repo.register_operation.assert_called_once()
        mock_stream_repo.session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reuses_existing_stream(self) -> None:
        orchestrator.configure(
            create_workbench_agent_fn=MagicMock(),
            resolve_model_id_fn=MagicMock(return_value="model-id"),
        )

        user_id = uuid4()
        existing_stream = MagicMock(id=uuid4())
        mock_user_repo = AsyncMock()
        mock_user_repo.get_or_create = AsyncMock()
        mock_stream_repo = AsyncMock()
        mock_stream_repo.find_by_experiment = AsyncMock(return_value=existing_stream)
        mock_stream_repo.register_operation = AsyncMock()
        mock_stream_repo.session = AsyncMock()
        mock_stream_repo.session.commit = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.workbench_chat.orchestrator.emit",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.workbench_chat.orchestrator.get_redis",
            ),
        ):
            _, stream_id = await orchestrator.start_workbench_chat_stream(
                message="What are the false positives?",
                site_id="plasmodb",
                experiment_id="exp-1",
                user_id=user_id,
                user_repo=mock_user_repo,
                stream_repo=mock_stream_repo,
            )

        assert stream_id == str(existing_stream.id)
        mock_stream_repo.create.assert_not_called()
