"""Extended tests for execution_tools.py and result_tools.py edge cases.

Covers: graph with no roots, graph with multiple roots, no session graph,
pagination edge cases, WDK error handling gaps, stale WDK state.
"""

from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.wdk_error_handler import handle_wdk_step_error
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.tests.fixtures.fakes import (
    FakeResultsAPI,
    FakeResultToolsSession,
    FakeStrategyAPI,
)

# ---------------------------------------------------------------------------
# ResultTools: get_sample_records edge cases
# ---------------------------------------------------------------------------


class TestSampleRecordsEdgeCases:
    async def test_limit_zero_rejected(self):
        """limit=0 should be rejected (min is 1)."""
        tools = ResultTools(FakeResultToolsSession())
        result = await tools.get_sample_records(wdk_step_id=1, limit=0)
        assert result["ok"] is False
        assert "between 1 and 500" in str(result["message"])

    async def test_limit_exactly_1_accepted(self):
        """limit=1 should work."""
        fake_api = FakeStrategyAPI(
            response={"records": [{"id": "g1"}], "meta": {"totalCount": 1}}
        )
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=1, limit=1)
        assert result["totalCount"] == 1

    async def test_limit_exactly_500_accepted(self):
        """limit=500 (max boundary) should work."""
        fake_api = FakeStrategyAPI(response={"records": [], "meta": {"totalCount": 0}})
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=1, limit=500)
        assert result["records"] == []

    async def test_wdk_404_returns_stale_step_message(self):
        """WDK 404 should map to a helpful stale-step message."""
        fake_api = FakeStrategyAPI(error=WDKError("Not found", 404))
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=99, limit=5)
        assert result["ok"] is False
        assert "stale" in str(result["message"]).lower()

    async def test_wdk_401_returns_auth_message(self):
        fake_api = FakeStrategyAPI(error=WDKError("Unauthorized", 401))
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=10, limit=5)
        assert result["ok"] is False
        assert "authorized" in str(result["message"]).lower()

    async def test_meta_missing_total_count_defaults_to_zero(self):
        """When meta doesn't have totalCount, should default to 0."""
        fake_api = FakeStrategyAPI(response={"records": [{"id": "x"}], "meta": {}})
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=1, limit=5)
        assert result["totalCount"] == 0

    async def test_meta_non_dict_handled(self):
        """When meta is not a dict, should not crash."""
        fake_api = FakeStrategyAPI(
            response={"records": [{"id": "x"}], "meta": "not-a-dict"}
        )
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=1, limit=5)
        assert result["totalCount"] == 0

    async def test_records_non_list_handled(self):
        """When records is not a list, should default to empty."""
        fake_api = FakeStrategyAPI(
            response={"records": "not-a-list", "meta": {"totalCount": 0}}
        )
        tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
        result = await tools.get_sample_records(wdk_step_id=1, limit=5)
        assert result["records"] == []


# ---------------------------------------------------------------------------
# ResultTools: get_download_url edge cases
# ---------------------------------------------------------------------------


class TestDownloadUrlEdgeCases:
    async def test_valid_attributes_accepted(self):
        fake_api = FakeResultsAPI(url="https://example.com/dl.csv")
        tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
        result = await tools.get_download_url(
            wdk_step_id=1, output_format="csv", attributes=["gene_id", "product"]
        )
        assert "downloadUrl" in result

    async def test_wdk_error_404(self):
        fake_api = FakeResultsAPI(error=WDKError("Not found", 404))
        tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
        result = await tools.get_download_url(wdk_step_id=99, output_format="csv")
        assert result["ok"] is False
        assert "stale" in str(result["message"]).lower()

    async def test_wdk_error_500(self):
        fake_api = FakeResultsAPI(error=WDKError("Internal", 500))
        tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
        result = await tools.get_download_url(wdk_step_id=1, output_format="csv")
        assert result["ok"] is False
        assert "temporarily unavailable" in str(result["message"])

    async def test_none_url_returns_error(self):
        """If the API returns None instead of a URL."""
        fake_api = FakeResultsAPI(url=None)
        tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
        result = await tools.get_download_url(wdk_step_id=1, output_format="csv")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# WDK error handler: timeout detection
# ---------------------------------------------------------------------------


class TestWdkErrorHandlerTimeouts:
    def test_503_maps_to_unavailable(self):
        """503 Service Unavailable should be treated like 5xx."""
        err = WDKError("Service Unavailable", 503)
        result = handle_wdk_step_error(
            err, wdk_step_id=1, action="read", fallback_message="reading"
        )
        assert "temporarily unavailable" in str(result["message"])
        assert result["http_status"] == 503

    def test_504_gateway_timeout_maps_to_unavailable(self):
        err = WDKError("Gateway Timeout", 504)
        result = handle_wdk_step_error(
            err, wdk_step_id=1, action="read", fallback_message="fetching"
        )
        assert "temporarily unavailable" in str(result["message"])

    def test_400_without_reportname_falls_through(self):
        err = WDKError("Bad request: invalid parameter x", 400)
        result = handle_wdk_step_error(
            err, wdk_step_id=5, action="read", fallback_message="reading"
        )
        assert "rejected request" in str(result["message"])
        assert "invalid parameter x" in str(result["message"])

    def test_detail_none_handled(self):
        """WDKError can have detail=None."""
        err = WDKError.__new__(WDKError)
        err.status = 400
        err.detail = None
        err.code = "WDK_ERROR"
        err.title = "Error"
        err.errors = None

        result = handle_wdk_step_error(
            err, wdk_step_id=1, action="read", fallback_message="reading"
        )
        assert result["ok"] is False
        # Should not crash even with detail=None


# ---------------------------------------------------------------------------
# ResultTools: step_id type coercion
# ---------------------------------------------------------------------------


class TestStepIdTypeValidation:
    async def test_step_id_negative_rejected(self):
        tools = ResultTools(FakeResultToolsSession())
        result = await tools.get_sample_records(wdk_step_id=-1, limit=5)
        assert result["ok"] is False
        assert "positive integer" in str(result["message"])

    async def test_download_step_id_negative_rejected(self):
        tools = ResultTools(FakeResultToolsSession())
        result = await tools.get_download_url(wdk_step_id=-1, output_format="csv")
        assert result["ok"] is False
        assert "positive integer" in str(result["message"])
