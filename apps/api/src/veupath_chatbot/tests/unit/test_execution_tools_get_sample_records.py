from __future__ import annotations

import pytest

from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.platform.errors import WDKError


class _FakeSession:
    def __init__(self) -> None:
        self.site_id = "plasmodb"

    def get_graph(self, graph_id: str | None):
        del graph_id
        return None


class _FakeStrategyAPI:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    async def get_step_answer(
        self, step_id: int, pagination: dict[str, int] | None = None
    ):
        del step_id
        del pagination
        if self._error is not None:
            raise self._error
        return self._response


@pytest.mark.asyncio
async def test_get_sample_records_validates_limit_range() -> None:
    tools = ExecutionTools(_FakeSession())

    result = await tools.get_sample_records(wdk_step_id=123, limit=0)

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "between 1 and 500" in str(result["message"])


@pytest.mark.asyncio
async def test_get_sample_records_validates_step_id() -> None:
    tools = ExecutionTools(_FakeSession())

    result = await tools.get_sample_records(wdk_step_id=0, limit=5)

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "positive integer" in str(result["message"])


@pytest.mark.asyncio
async def test_get_sample_records_maps_wdk_404_to_actionable_error() -> None:
    tools = ExecutionTools(_FakeSession())
    fake_api = _FakeStrategyAPI(
        error=WDKError("GET /users/current/steps/1 -> HTTP 404", 404)
    )
    tools._get_api = lambda: fake_api

    result = await tools.get_sample_records(wdk_step_id=437637423, limit=50)

    assert result["ok"] is False
    assert result["code"] == "WDK_ERROR"
    assert "Step not found in VEuPathDB" in str(result["message"])
    assert "stale" in str(result["message"])
    assert result["wdk_step_id"] == 437637423


@pytest.mark.asyncio
async def test_get_sample_records_returns_records_total_and_attributes() -> None:
    tools = ExecutionTools(_FakeSession())
    fake_api = _FakeStrategyAPI(
        response={
            "records": [{"record_primary_key": "A", "display_name": "alpha"}],
            "meta": {"totalCount": 17},
        }
    )
    tools._get_api = lambda: fake_api

    result = await tools.get_sample_records(wdk_step_id=123, limit=5)

    assert result["records"] == [{"record_primary_key": "A", "display_name": "alpha"}]
    assert result["totalCount"] == 17
    assert result["attributes"] == ["record_primary_key", "display_name"]
