"""Unit tests for WDK step counts — caching, leaf detection, cache eviction."""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKAnswerMeta,
)
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies import wdk_counts
from veupath_chatbot.services.strategies.schemas import StrategyPlanPayload
from veupath_chatbot.services.strategies.wdk_counts import (
    _STEP_COUNTS_CACHE,
    _cache_counts,
    compute_step_counts_for_plan,
    is_leaf_only_plan,
    plan_cache_key,
)


def _simple_ast() -> StrategyPlanPayload:
    return StrategyPlanPayload(
        record_type="gene",
        root=PlanStepNode(
            search_name="GenesByTextSearch",
            parameters={"text_expression": "kinase"},
            id="step1",
        ),
    )


def _two_leaf_ast() -> StrategyPlanPayload:
    """Two leaf steps (no combine)."""
    left = PlanStepNode(search_name="GenesByTaxon", parameters={"org": "pfal"}, id="s1")
    right = PlanStepNode(search_name="GenesByText", parameters={"q": "kinase"}, id="s2")
    return StrategyPlanPayload(
        record_type="gene",
        root=PlanStepNode(
            search_name="boolean_question",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
            id="s3",
        ),
    )


def _transform_ast() -> StrategyPlanPayload:
    """Transform step (primary input only)."""
    child = PlanStepNode(
        search_name="GenesByTaxon", parameters={"org": "pfal"}, id="s1"
    )
    return StrategyPlanPayload(
        record_type="gene",
        root=PlanStepNode(
            search_name="GenesByOrthologPattern",
            primary_input=child,
            parameters={"pattern": "%PFAL:Y%"},
            id="s2",
        ),
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the module-level cache before each test."""
    wdk_counts._STEP_COUNTS_CACHE.clear()
    yield
    wdk_counts._STEP_COUNTS_CACHE.clear()


# ── plan_cache_key ────────────────────────────────────────────────


class TestPlanCacheKey:
    def test_deterministic(self) -> None:
        plan = {"recordType": "gene", "root": {"searchName": "S1"}}
        key1 = plan_cache_key("plasmodb", plan)
        key2 = plan_cache_key("plasmodb", plan)
        assert key1 == key2

    def test_different_site_different_key(self) -> None:
        plan = {"recordType": "gene", "root": {"searchName": "S1"}}
        assert plan_cache_key("plasmodb", plan) != plan_cache_key("toxodb", plan)

    def test_different_plan_different_key(self) -> None:
        plan_a = {"recordType": "gene", "root": {"searchName": "S1"}}
        plan_b = {"recordType": "gene", "root": {"searchName": "S2"}}
        assert plan_cache_key("plasmodb", plan_a) != plan_cache_key("plasmodb", plan_b)

    def test_key_order_irrelevant(self) -> None:
        """sort_keys=True ensures key ordering doesn't affect hash."""
        plan_a = {"b": 2, "a": 1}
        plan_b = {"a": 1, "b": 2}
        assert plan_cache_key("site", plan_a) == plan_cache_key("site", plan_b)

    def test_format_is_site_colon_hash(self) -> None:
        key = plan_cache_key("plasmodb", {})
        assert key.startswith("plasmodb:")
        assert len(key.split(":")[1]) == 64  # SHA-256 hex digest


# ── is_leaf_only_strategy ─────────────────────────────────────────


class TestIsLeafOnlyPlan:
    def test_single_search_step(self) -> None:
        assert is_leaf_only_plan(_simple_ast().root) is True

    def test_combine_step_is_not_leaf_only(self) -> None:
        assert is_leaf_only_plan(_two_leaf_ast().root) is False

    def test_transform_step_is_not_leaf_only(self) -> None:
        assert is_leaf_only_plan(_transform_ast().root) is False

    def test_two_search_steps_without_combine(self) -> None:
        """A plan with only search steps but no combine is leaf-only."""
        payload = _simple_ast()
        assert is_leaf_only_plan(payload.root) is True


# ── Cache eviction ────────────────────────────────────────────────


class TestCacheEviction:
    def test_lru_eviction_at_max(self) -> None:
        """When cache exceeds max, oldest entry should be evicted."""
        maxsize = _STEP_COUNTS_CACHE.maxsize

        # Fill cache to max
        for i in range(maxsize):
            _cache_counts(f"key_{i}", {f"step_{i}": i})
        assert len(_STEP_COUNTS_CACHE) == maxsize

        # Add one more — should evict oldest (key_0)
        _cache_counts("new_key", {"new_step": 999})
        assert len(_STEP_COUNTS_CACHE) == maxsize
        assert "key_0" not in _STEP_COUNTS_CACHE
        assert "new_key" in _STEP_COUNTS_CACHE
        assert _STEP_COUNTS_CACHE["new_key"] == {"new_step": 999}

    def test_cache_hit_promotes_entry(self) -> None:
        """Accessing a cached entry should promote it (prevent eviction)."""
        maxsize = _STEP_COUNTS_CACHE.maxsize

        _cache_counts("old", {"s": 1})
        _cache_counts("mid", {"s": 2})
        _cache_counts("new", {"s": 3})

        # Access "old" to promote it in the LRU
        _ = _STEP_COUNTS_CACHE["old"]

        # Fill to max and evict — "mid" should be evicted before "old"
        for i in range(maxsize - 3):
            _cache_counts(f"fill_{i}", {})
        _cache_counts("overflow", {})

        assert "old" in _STEP_COUNTS_CACHE
        assert "mid" not in _STEP_COUNTS_CACHE


# ── compute_step_counts_for_plan — caching ────────────────────────


@pytest.mark.asyncio
async def test_all_none_results_are_cached():
    """All-None results must be cached to avoid repeated expensive API calls.

    When the WDK API fails to return counts, compute_step_counts_for_plan
    returns {step_id: None} for every step.  Previously this was never
    cached, causing repeated create-fetch-delete cycles on every call.

    For leaf-only strategies, the function now uses anonymous reports
    (not compilation), so we mock ``client.run_search_report``.
    """
    plan = _simple_ast().model_dump(by_alias=True, exclude_none=True, mode="json")
    ast = _simple_ast()

    mock_client = AsyncMock()
    # Anonymous report raises WDKError (simulates WDK failure)
    mock_client.run_search_report.side_effect = WDKError("WDK unavailable", status=503)

    mock_api = AsyncMock()
    mock_api.client = mock_client

    with patch(
        "veupath_chatbot.services.strategies.wdk_counts.get_strategy_api",
        return_value=mock_api,
    ):
        # First call — should hit the API
        result1 = await compute_step_counts_for_plan(plan, ast, "plasmodb")
        assert result1 == {"step1": None}

        # Second call — should hit cache, NOT the API again
        result2 = await compute_step_counts_for_plan(plan, ast, "plasmodb")
        assert result2 == {"step1": None}

    assert len(_STEP_COUNTS_CACHE) == 1


# ── compute_step_counts_for_plan — success path ──────────────────


@pytest.mark.asyncio
async def test_successful_leaf_count():
    """Successful anonymous report returns actual count."""
    ast = _simple_ast()
    plan = ast.model_dump(by_alias=True, exclude_none=True, mode="json")

    mock_answer = WDKAnswer(
        meta=WDKAnswerMeta(total_count=5000, display_total_count=0),
        records=[],
    )
    mock_client = AsyncMock()
    mock_client.run_search_report.return_value = mock_answer

    mock_api = AsyncMock()
    mock_api.client = mock_client

    with patch(
        "veupath_chatbot.services.strategies.wdk_counts.get_strategy_api",
        return_value=mock_api,
    ):
        result = await compute_step_counts_for_plan(plan, ast, "plasmodb")

    assert result == {"step1": 5000}


@pytest.mark.asyncio
async def test_different_sites_not_cached_together():
    """Same plan on different sites should have separate cache entries."""
    ast = _simple_ast()
    plan = ast.model_dump(by_alias=True, exclude_none=True, mode="json")

    mock_answer = WDKAnswer(
        meta=WDKAnswerMeta(total_count=100, display_total_count=0),
        records=[],
    )
    mock_client = AsyncMock()
    mock_client.run_search_report.return_value = mock_answer
    mock_api = AsyncMock()
    mock_api.client = mock_client

    with patch(
        "veupath_chatbot.services.strategies.wdk_counts.get_strategy_api",
        return_value=mock_api,
    ):
        result_plasmo = await compute_step_counts_for_plan(plan, ast, "plasmodb")
        result_toxo = await compute_step_counts_for_plan(plan, ast, "toxodb")

    assert result_plasmo == {"step1": 100}
    assert result_toxo == {"step1": 100}
    # Two separate cache entries — one per site
    assert len(_STEP_COUNTS_CACHE) == 2
