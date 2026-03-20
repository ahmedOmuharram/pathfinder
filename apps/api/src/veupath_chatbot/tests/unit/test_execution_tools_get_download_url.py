import pytest

from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.platform.errors import DataParsingError, WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.tests.fixtures.fakes import (
    FakeResultsAPI,
    FakeResultToolsSession,
)


class _CaptureClient:
    def __init__(
        self,
        *,
        post_response: JSONObject | None = None,
        base_url: str = "https://example.org/service",
    ) -> None:
        self.last_path: str | None = None
        self.last_json: JSONObject | None = None
        self.base_url = base_url
        self._post_response = (
            post_response if post_response is not None else {"id": "tmp-1"}
        )

    async def get(self, path: str):
        if path == "/users/current":
            return {}
        return {}

    async def post(self, path: str, json: JSONObject | None = None):
        self.last_path = path
        self.last_json = json
        return self._post_response


@pytest.mark.asyncio
async def test_get_download_url_validates_format() -> None:
    tools = ResultTools(FakeResultToolsSession())

    result = await tools.get_download_url(wdk_step_id=123, output_format="xlsx")

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "csv, tab, json" in str(result["message"])


@pytest.mark.asyncio
async def test_get_download_url_maps_report_name_payload_error() -> None:
    fake_api = FakeResultsAPI(
        error=WDKError(
            'POST /temporary-results -> HTTP 400: JSONObject["reportName"] not found.',
            400,
        )
    )
    tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)

    result = await tools.get_download_url(
        wdk_step_id=437637443,
        output_format="csv",
        attributes=["primary_key"],
    )

    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"
    assert "reportName" in str(result["message"])
    assert result["wdk_step_id"] == 437637443


@pytest.mark.asyncio
async def test_get_download_url_returns_url_on_success() -> None:
    fake_api = FakeResultsAPI(url="https://example/download.csv")
    tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)

    result = await tools.get_download_url(
        wdk_step_id=101, output_format="csv", attributes=None
    )

    assert result["downloadUrl"] == "https://example/download.csv"
    assert result["format"] == "csv"
    assert result["stepId"] == 101


@pytest.mark.asyncio
async def test_create_temporary_result_uses_report_name_field() -> None:
    client = _CaptureClient()
    api = TemporaryResultsAPI(client)

    await api.create_temporary_result(step_id=437637443, reporter="standard")

    assert client.last_path == "/temporary-results"
    assert client.last_json is not None
    assert client.last_json.get("reportName") == "standard"
    assert "reporterName" not in client.last_json


@pytest.mark.asyncio
async def test_temporary_results_get_download_url_constructs_from_id() -> None:
    client = _CaptureClient(post_response={"id": "tmp-1"})
    api = TemporaryResultsAPI(client)

    url = await api.get_download_url(step_id=123, output_format="csv", attributes=None)

    assert url == "https://example.org/service/temporary-results/tmp-1"


@pytest.mark.asyncio
async def test_temporary_results_get_download_url_raises_when_no_id() -> None:
    client = _CaptureClient(post_response={})
    api = TemporaryResultsAPI(client)

    with pytest.raises(DataParsingError, match=r"did not include.*id"):
        await api.get_download_url(step_id=123, output_format="csv", attributes=None)
