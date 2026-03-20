"""Tests for the user data purge service (services/user_data.py)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from veupath_chatbot.services.user_data import (
    PurgeResult,
    _purge_wdk_strategies,
    purge_user_data,
)


def _make_stream(stream_id: UUID | None = None, site_id: str = "plasmodb") -> MagicMock:
    s = MagicMock()
    s.id = stream_id or uuid4()
    s.site_id = site_id
    return s


class TestPurgeUserData:
    """Test the purge service function."""

    @pytest.mark.asyncio
    async def test_returns_purge_result(self) -> None:
        session = AsyncMock()
        redis = MagicMock()
        redis.delete = AsyncMock(return_value=1)
        user_id = uuid4()

        # Mock session.execute to return empty results for all queries
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        session.execute = AsyncMock(
            side_effect=[mock_result, mock_cursor, mock_cursor, mock_cursor]
        )

        with (
            patch(
                "veupath_chatbot.services.user_data._purge_wdk_strategies",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "veupath_chatbot.services.user_data._clear_gene_set_cache",
            ),
        ):
            result = await purge_user_data(
                session=session,
                redis=redis,
                user_id=user_id,
                site_id=None,
                delete_wdk=False,
            )

        assert isinstance(result, PurgeResult)
        assert result.wdk_strategies == 0

    @pytest.mark.asyncio
    async def test_dismiss_mode_does_not_hard_delete_streams(self) -> None:
        """When delete_wdk=False, WDK-linked streams are dismissed, not deleted."""
        session = AsyncMock()
        redis = MagicMock()
        redis.delete = AsyncMock(return_value=1)
        user_id = uuid4()

        streams = [_make_stream(), _make_stream()]
        mock_stream_result = MagicMock()
        mock_stream_result.scalars.return_value.all.return_value = streams

        # dismiss update, then 3 deletes (gene sets, experiments, control sets)
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        session.execute = AsyncMock(
            side_effect=[
                mock_stream_result,
                None,
                mock_cursor,
                mock_cursor,
                mock_cursor,
            ]
        )

        with (
            patch(
                "veupath_chatbot.services.user_data._purge_wdk_strategies",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "veupath_chatbot.services.user_data._clear_gene_set_cache",
            ),
        ):
            result = await purge_user_data(
                session=session,
                redis=redis,
                user_id=user_id,
                site_id=None,
                delete_wdk=False,
            )

        # Should dismiss, not hard-delete
        assert result.dismissed == 2
        assert result.hard_deleted == 0


class TestPurgeWdkStrategies:
    """Test WDK strategy deletion."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_disabled(self) -> None:
        result = await _purge_wdk_strategies(site_id=None, delete_wdk=False)
        assert result == 0

    @pytest.mark.asyncio
    async def test_deletes_strategies_when_enabled(self) -> None:
        mock_api = AsyncMock()
        mock_api.list_strategies = AsyncMock(
            return_value=[{"strategyId": 1}, {"strategyId": 2}]
        )
        mock_api.delete_strategy = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.user_data.get_strategy_api",
                return_value=mock_api,
            ),
            patch(
                "veupath_chatbot.services.user_data.list_sites",
                return_value=[MagicMock(id="plasmodb")],
            ),
        ):
            result = await _purge_wdk_strategies(site_id=None, delete_wdk=True)

        assert result == 2
        assert mock_api.delete_strategy.call_count == 2
