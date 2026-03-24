"""Tests for the simplified get_download_url that constructs URL from POST id.

WDK POST /temporary-results returns {"id": "abc123"}, and the download
is available at {base_url}/temporary-results/{id}/result.  No polling needed.
"""

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI


def _make_api(
    base_url: str = "https://plasmodb.org/plasmo/service",
    user_id: str = "12345",
) -> tuple[TemporaryResultsAPI, MagicMock]:
    """Create TemporaryResultsAPI with a mocked client that has base_url."""
    client = MagicMock()
    client.base_url = base_url
    client.get = AsyncMock()
    client.post = AsyncMock()
    api = TemporaryResultsAPI(client)
    api._resolved_user_id = user_id
    api._session_initialized = True
    return api, client


# ---------------------------------------------------------------------------
# URL construction from POST response
# ---------------------------------------------------------------------------


class TestGetDownloadUrlConstructsUrl:
    """get_download_url constructs URL from the POST response id."""

    async def test_constructs_url_from_id(self) -> None:
        api, client = _make_api()
        client.post.return_value = {"id": "abc123"}

        url = await api.get_download_url(step_id=42, output_format="csv")

        assert url == "https://plasmodb.org/plasmo/service/temporary-results/abc123"

    async def test_url_constructed_without_polling(self) -> None:
        """URL is constructed from POST response, not polled for."""
        api, client = _make_api()
        client.post.return_value = {"id": "result-99"}

        url = await api.get_download_url(step_id=42, output_format="csv")

        assert "temporary-results/result-99" in url

    async def test_different_base_url(self) -> None:
        api, client = _make_api(base_url="https://toxodb.org/toxo/service")
        client.post.return_value = {"id": "tmp-xyz"}

        url = await api.get_download_url(step_id=10, output_format="tab")

        assert url == "https://toxodb.org/toxo/service/temporary-results/tmp-xyz"

    async def test_base_url_trailing_slash_stripped(self) -> None:
        api, client = _make_api(base_url="https://example.org/service/")
        client.post.return_value = {"id": "r1"}

        url = await api.get_download_url(step_id=1, output_format="csv")

        # VEuPathDBClient already strips trailing slash, but be safe
        assert "/service//temporary" not in url
        assert "temporary-results/r1" in url

    async def test_raises_when_no_id_in_response(self) -> None:
        api, client = _make_api()
        client.post.return_value = {}

        with pytest.raises(pydantic.ValidationError):
            await api.get_download_url(step_id=42, output_format="csv")


# ---------------------------------------------------------------------------
# Format / reporter mapping (unchanged behavior, but verified post-refactor)
# ---------------------------------------------------------------------------


class TestGetDownloadUrlFormats:
    """Format configuration is still sent correctly to POST."""

    async def test_csv_format_config(self) -> None:
        api, client = _make_api()
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, output_format="csv")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "standard"
        config = payload["reportConfig"]
        assert config["type"] == "standard"
        assert config["includeHeader"] is True
        assert config["attachmentType"] == "text"

    async def test_tab_format_config(self) -> None:
        api, client = _make_api()
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, output_format="tab")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "standard"
        config = payload["reportConfig"]
        assert config["type"] == "standard"

    async def test_json_format_config(self) -> None:
        api, client = _make_api()
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, output_format="json")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "fullRecord"
        config = payload["reportConfig"]
        assert config["type"] == "json"

    async def test_attributes_passed_through(self) -> None:
        api, client = _make_api()
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(
            step_id=42, output_format="csv", attributes=["gene_name", "product"]
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"]["attributes"] == ["gene_name", "product"]
