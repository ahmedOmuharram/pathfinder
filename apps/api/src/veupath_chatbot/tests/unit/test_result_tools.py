"""Tests for ai.tools.result_tools -- validation and response formatting.

Supplements the existing test_execution_tools_get_*.py files with edge cases.
"""

from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.tests.fixtures.fakes import (
    FakeResultsAPI,
    FakeResultToolsSession,
    FakeStrategyAPI,
)

# -- get_download_url validation --


async def test_download_url_validates_step_id_zero():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_download_url(wdk_step_id=0, output_format="csv")
    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "positive integer" in str(result["message"])


async def test_download_url_validates_step_id_negative():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_download_url(wdk_step_id=-5, output_format="csv")
    assert result["ok"] is False
    assert "positive integer" in str(result["message"])


async def test_download_url_validates_format_unknown():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_download_url(wdk_step_id=1, output_format="xml")
    assert result["ok"] is False
    assert "csv, tab, json" in str(result["message"])


async def test_download_url_rejects_empty_attributes_list():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_download_url(
        wdk_step_id=1, output_format="csv", attributes=[]
    )
    assert result["ok"] is False
    assert "empty list" in str(result["message"])


async def test_download_url_rejects_blank_attributes():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_download_url(
        wdk_step_id=1, output_format="csv", attributes=["good", "", "  "]
    )
    assert result["ok"] is False
    assert "non-empty strings" in str(result["message"])


async def test_download_url_accepts_all_valid_formats():
    for fmt in ("csv", "tab", "json"):
        fake_api = FakeResultsAPI(url=f"https://example/dl.{fmt}")
        tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
        result = await tools.get_download_url(wdk_step_id=1, output_format=fmt)
        assert "downloadUrl" in result, f"Failed for format={fmt}"


async def test_download_url_handles_empty_url_from_api():
    fake_api = FakeResultsAPI(url="")
    tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
    result = await tools.get_download_url(wdk_step_id=1, output_format="csv")
    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"


async def test_download_url_handles_generic_exception():
    fake_api = FakeResultsAPI(error=OSError("Connection reset"))
    tools = ResultTools(FakeResultToolsSession(), results_api=fake_api)
    result = await tools.get_download_url(wdk_step_id=1, output_format="csv")
    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"
    assert "Connection reset" in str(result.get("detail", ""))


# -- get_sample_records validation --


async def test_sample_records_limit_too_high():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_sample_records(wdk_step_id=1, limit=501)
    assert result["ok"] is False
    assert "between 1 and 500" in str(result["message"])


async def test_sample_records_limit_negative():
    tools = ResultTools(FakeResultToolsSession())
    result = await tools.get_sample_records(wdk_step_id=1, limit=-1)
    assert result["ok"] is False


async def test_sample_records_empty_records_list():
    fake_api = FakeStrategyAPI(response={"records": [], "meta": {"totalCount": 0}})
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
    result = await tools.get_sample_records(wdk_step_id=1, limit=5)
    assert result["records"] == []
    assert result["totalCount"] == 0
    assert result["attributes"] == []


async def test_sample_records_non_dict_response_raises():
    fake_api = FakeStrategyAPI(response="not a dict")
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
    result = await tools.get_sample_records(wdk_step_id=1, limit=5)
    # Should be caught by the generic exception handler
    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"


async def test_sample_records_wdk_500_error():
    fake_api = FakeStrategyAPI(error=WDKError("Internal Server Error", 500))
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
    result = await tools.get_sample_records(wdk_step_id=1, limit=5)
    assert result["ok"] is False
    assert "temporarily unavailable" in str(result["message"])


async def test_sample_records_extracts_attributes_from_first_record():
    fake_api = FakeStrategyAPI(
        response={
            "records": [
                {"gene_id": "PF3D7_001", "organism": "P. falciparum"},
                {"gene_id": "PF3D7_002", "organism": "P. vivax"},
            ],
            "meta": {"totalCount": 42},
        }
    )
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)
    result = await tools.get_sample_records(wdk_step_id=1, limit=5)
    assert result["totalCount"] == 42
    assert result["attributes"] == ["gene_id", "organism"]
    assert len(result["records"]) == 2
