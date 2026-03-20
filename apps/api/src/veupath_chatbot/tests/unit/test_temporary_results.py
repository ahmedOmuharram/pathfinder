"""Unit tests for veupath_chatbot.integrations.veupathdb.temporary_results.

Tests TemporaryResultsAPI: create_temporary_result, get_download_url,
and get_step_preview.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.platform.errors import DataParsingError


def _make_api(
    user_id: str = "current",
    base_url: str = "https://plasmodb.org/plasmo/service",
) -> tuple[TemporaryResultsAPI, MagicMock]:
    """Create TemporaryResultsAPI with a mocked client."""
    client = MagicMock()
    client.base_url = base_url
    client.get = AsyncMock()
    client.post = AsyncMock()
    api = TemporaryResultsAPI(client)
    api.user_id = user_id
    return api, client


# ---------------------------------------------------------------------------
# _ensure_session
# ---------------------------------------------------------------------------


class TestEnsureSession:
    """Session resolution resolves the WDK user ID once."""

    async def test_resolves_user_id(self) -> None:
        api, _client = _make_api()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value="12345",
        ):
            await api._ensure_session()
        assert api.user_id == "12345"
        assert api._session_initialized is True

    async def test_does_not_resolve_twice(self) -> None:
        api, _client = _make_api()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value="12345",
        ) as mock_resolve:
            await api._ensure_session()
            await api._ensure_session()
        mock_resolve.assert_awaited_once()

    async def test_keeps_current_if_resolve_returns_none(self) -> None:
        api, _client = _make_api()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await api._ensure_session()
        assert api.user_id == "current"


# ---------------------------------------------------------------------------
# create_temporary_result
# ---------------------------------------------------------------------------


class TestCreateTemporaryResult:
    """Tests for creating temporary results."""

    async def test_basic_creation(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "abc123"}

        result = await api.create_temporary_result(step_id=42)

        client.post.assert_awaited_once_with(
            "/temporary-results",
            json={
                "stepId": 42,
                "reportName": "standard",
            },
        )
        assert result["id"] == "abc123"

    async def test_custom_reporter_and_format_config(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "abc"}

        config = {"type": "json"}
        await api.create_temporary_result(
            step_id=42, reporter="fullRecord", format_config=config
        )

        call_args = client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["reportName"] == "fullRecord"
        assert payload["reportConfig"] == {"type": "json"}

    async def test_uses_report_name_not_reporter_name(self) -> None:
        """WDK requires 'reportName', not 'reporterName' (see source comment)."""
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "x"}

        await api.create_temporary_result(step_id=1)

        payload = client.post.call_args.kwargs["json"]
        assert "reportName" in payload
        assert "reporterName" not in payload


# ---------------------------------------------------------------------------
# get_download_url
# ---------------------------------------------------------------------------


class TestGetDownloadUrl:
    """Tests for get_download_url which creates a temp result and constructs URL."""

    async def test_constructs_url_from_id(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "result1"}

        url = await api.get_download_url(step_id=42, output_format="csv")

        assert url == "https://plasmodb.org/plasmo/service/temporary-results/result1"

    async def test_csv_format_uses_standard_reporter(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, output_format="csv")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "standard"

    async def test_json_format_uses_full_record_reporter(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, output_format="json")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "fullRecord"

    async def test_with_attributes(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(
            step_id=42, output_format="csv", attributes=["gene_name", "product"]
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload.get("reportConfig", {}).get("attributes") == [
            "gene_name",
            "product",
        ]

    async def test_no_polling_needed(self) -> None:
        """GET is never called -- URL is constructed from POST response id."""
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"id": "result1"}

        await api.get_download_url(step_id=42, output_format="csv")

        client.get.assert_not_awaited()

    async def test_raises_when_no_id(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {}

        with pytest.raises(DataParsingError, match=r"did not include.*id"):
            await api.get_download_url(step_id=42, output_format="csv")


# ---------------------------------------------------------------------------
# get_step_preview
# ---------------------------------------------------------------------------


class TestGetStepPreview:
    """Tests for get_step_preview which uses the standard report endpoint."""

    async def test_basic_preview(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {
            "records": [{"id": [{"name": "source_id", "value": "PF3D7_0100100"}]}],
            "meta": {"totalCount": 1},
        }

        await api.get_step_preview(step_id=42, limit=10)

        client.post.assert_awaited_once()
        call_args = client.post.call_args
        assert "/steps/42/reports/standard" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["reportConfig"]["pagination"]["numRecords"] == 10

    async def test_preview_with_attributes(self) -> None:
        api, client = _make_api("12345")
        api._session_initialized = True
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}

        await api.get_step_preview(step_id=42, attributes=["gene_name", "product"])

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"]["attributes"] == ["gene_name", "product"]
