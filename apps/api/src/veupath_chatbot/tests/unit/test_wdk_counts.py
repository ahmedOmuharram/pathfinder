"""Unit tests for WDK step counts caching."""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.services.strategies import wdk_counts
from veupath_chatbot.services.strategies.wdk_counts import (
    _STEP_COUNTS_CACHE,
    compute_step_counts_for_plan,
)


def _simple_ast() -> StrategyAST:
    return StrategyAST(
        record_type="gene",
        root=PlanStepNode(
            search_name="GenesByTextSearch",
            parameters={"text_expression": "kinase"},
            id="step1",
        ),
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the module-level cache before each test."""
    wdk_counts._STEP_COUNTS_CACHE.clear()
    yield
    wdk_counts._STEP_COUNTS_CACHE.clear()


@pytest.mark.asyncio
async def test_all_none_results_are_cached():
    """All-None results must be cached to avoid repeated expensive API calls.

    When the WDK API fails to return counts, compute_step_counts_for_plan
    returns {step_id: None} for every step.  Previously this was never
    cached, causing repeated create-fetch-delete cycles on every call.

    For leaf-only strategies, the function now uses anonymous reports
    (not compilation), so we mock ``client.run_search_report``.
    """
    plan = _simple_ast().to_dict()
    ast = _simple_ast()

    mock_client = AsyncMock()
    # Anonymous report returns no totalCount (simulates WDK failure)
    mock_client.run_search_report.return_value = {"meta": {}}

    mock_api = AsyncMock()
    mock_api.client = mock_client

    with patch(
        "veupath_chatbot.services.strategies.wdk_counts.get_strategy_api",
        return_value=mock_api,
    ):
        # First call — should hit the API
        result1 = await compute_step_counts_for_plan(plan, ast, "plasmodb")
        assert result1 == {"step1": None}
        assert mock_client.run_search_report.call_count == 1

        # Second call — should hit cache, NOT the API again
        result2 = await compute_step_counts_for_plan(plan, ast, "plasmodb")
        assert result2 == {"step1": None}
        assert mock_client.run_search_report.call_count == 1, (
            "Expected cache hit — API should NOT be called again for all-None results"
        )

    assert len(_STEP_COUNTS_CACHE) == 1
