import pytest

from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.tests.fixtures.fakes import (
    FakeResultToolsSession,
    FakeStrategyAPI,
)


@pytest.mark.asyncio
async def test_get_sample_records_validates_limit_range() -> None:
    tools = ResultTools(FakeResultToolsSession())

    result = await tools.get_sample_records(wdk_step_id=123, limit=0)

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "between 1 and 500" in str(result["message"])


@pytest.mark.asyncio
async def test_get_sample_records_validates_step_id() -> None:
    tools = ResultTools(FakeResultToolsSession())

    result = await tools.get_sample_records(wdk_step_id=0, limit=5)

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "positive integer" in str(result["message"])


@pytest.mark.asyncio
async def test_get_sample_records_maps_wdk_404_to_actionable_error() -> None:
    fake_api = FakeStrategyAPI(
        error=WDKError("GET /users/current/steps/1 -> HTTP 404", 404)
    )
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)

    result = await tools.get_sample_records(wdk_step_id=437637423, limit=50)

    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"
    assert "Step not found in VEuPathDB" in str(result["message"])
    assert "stale" in str(result["message"])
    assert result["wdk_step_id"] == 437637423


@pytest.mark.asyncio
async def test_get_sample_records_returns_records_total_and_attributes() -> None:
    fake_api = FakeStrategyAPI(
        response={
            "records": [
                {
                    "id": [{"name": "source_id", "value": "A"}],
                    "displayName": "alpha",
                    "attributes": {"record_primary_key": "A", "display_name": "alpha"},
                }
            ],
            "meta": {"totalCount": 17},
        }
    )
    tools = ResultTools(FakeResultToolsSession(), strategy_api=fake_api)

    result = await tools.get_sample_records(wdk_step_id=123, limit=5)

    assert result["totalCount"] == 17
    assert result["attributes"] == ["record_primary_key", "display_name"]
    assert len(result["records"]) == 1
    assert result["records"][0]["attributes"] == {
        "record_primary_key": "A",
        "display_name": "alpha",
    }
