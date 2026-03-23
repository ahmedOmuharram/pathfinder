"""Tests for the strategy build service (services/strategies/build.py).

Covers: root resolution, step count extraction, and result count lookup.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.searches import resolve_record_type_from_steps
from veupath_chatbot.services.strategies.build import (
    RootResolutionError,
    StepCountResult,
    extract_step_counts,
    get_estimated_size,
    resolve_root_step,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeCountAPI:
    """Fake API satisfying StepCountAPI for testing."""

    def __init__(
        self,
        *,
        get_strategy_response: WDKStrategyDetails | None = None,
        step_count: int = 42,
    ) -> None:
        self._get_strategy_response = get_strategy_response or _make_strategy_details()
        self._step_count = step_count

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        return self._get_strategy_response

    async def get_step_count(self, step_id: int) -> int:
        return self._step_count


def _make_graph(
    *,
    site_id: str = "plasmodb",
    name: str = "Test Graph",
    record_type: str | None = "gene",
) -> StrategyGraph:
    graph = StrategyGraph("g1", name, site_id)
    graph.record_type = record_type
    return graph


def _make_step(
    step_id: str = "step_1",
    search_name: str = "GenesByTaxon",
    parameters: JSONObject | None = None,
) -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        parameters=parameters or {},
        id=step_id,
    )


# ---------------------------------------------------------------------------
# resolve_root_step
# ---------------------------------------------------------------------------


class TestResolveRootStep:
    def test_explicit_root_step_found(self):
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)
        result = resolve_root_step(graph, "s1")
        assert result.id == "s1"

    def test_explicit_root_step_not_found(self):
        graph = _make_graph()
        with pytest.raises(RootResolutionError, match="not found"):
            resolve_root_step(graph, "nonexistent")

    def test_single_root_auto_resolved(self):
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)
        result = resolve_root_step(graph, None)
        assert result.id == "s1"

    def test_multiple_roots_raises(self):
        graph = _make_graph()
        graph.add_step(_make_step("s1"))
        graph.add_step(_make_step("s2", search_name="GenesByLocation"))
        with pytest.raises(RootResolutionError, match="subtree roots"):
            resolve_root_step(graph, None)

    def test_no_roots_raises(self):
        graph = _make_graph()
        with pytest.raises(RootResolutionError, match="No steps"):
            resolve_root_step(graph, None)


# ---------------------------------------------------------------------------
# resolve_record_type_from_steps
# ---------------------------------------------------------------------------


class TestResolveRecordTypeFromSteps:
    async def test_resolves_from_leaf_search(self):
        step = _make_step("s1", search_name="GenesByTaxon")

        async def resolver(search_name: str) -> str | None:
            return "gene" if search_name == "GenesByTaxon" else None

        result = await resolve_record_type_from_steps(step, resolver)
        assert result == "gene"

    async def test_resolves_from_nested_leaf(self):
        """Walks through transform/combine to find leaf search."""
        leaf_a = _make_step("a", search_name="GenesByTaxon")
        leaf_b = _make_step("b", search_name="GenesByLocation")
        combine = PlanStepNode(
            search_name="__combine__",
            id="c",
            operator=CombineOp.INTERSECT,
            primary_input=leaf_a,
            secondary_input=leaf_b,
        )

        async def resolver(search_name: str) -> str | None:
            return (
                "gene" if search_name in ("GenesByTaxon", "GenesByLocation") else None
            )

        result = await resolve_record_type_from_steps(combine, resolver)
        assert result == "gene"

    async def test_returns_none_when_no_leaf_resolves(self):
        step = _make_step("s1", search_name="UnknownSearch")

        async def resolver(search_name: str) -> str | None:
            return None

        result = await resolve_record_type_from_steps(step, resolver)
        assert result is None

    async def test_returns_first_resolved(self):
        """If multiple leaves, returns the first one that resolves."""
        leaf_a = _make_step("a", search_name="UnknownSearch")
        leaf_b = _make_step("b", search_name="GenesByLocation")
        combine = PlanStepNode(
            search_name="__combine__",
            id="c",
            operator=CombineOp.INTERSECT,
            primary_input=leaf_a,
            secondary_input=leaf_b,
        )

        async def resolver(search_name: str) -> str | None:
            return "gene" if search_name == "GenesByLocation" else None

        result = await resolve_record_type_from_steps(combine, resolver)
        assert result == "gene"


# ---------------------------------------------------------------------------
# extract_step_counts
# ---------------------------------------------------------------------------


def _make_strategy_details(
    root_step_id: int = 100,
    steps: dict[str, dict[str, object]] | None = None,
    strategy_id: int = 1,
) -> WDKStrategyDetails:
    """Build a WDKStrategyDetails from step data for tests."""
    raw_steps = steps or {}
    return WDKStrategyDetails.model_validate(
        {
            "strategyId": strategy_id,
            "name": "Test",
            "rootStepId": root_step_id,
            "stepTree": {"stepId": root_step_id},
            "steps": {
                k: {
                    "id": int(k) if k.isdigit() else 0,
                    "searchName": "TestSearch",
                    "searchConfig": {"parameters": {}},
                    **v,
                }
                for k, v in raw_steps.items()
            },
        }
    )


class TestExtractStepCounts:
    def test_basic_extraction(self):
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "100": {"estimatedSize": 42},
                "200": {"estimatedSize": 0},
            },
        )
        compiled_map = {"s1": 100, "s2": 200}
        counts, root_count = extract_step_counts(strategy_info, compiled_map)
        assert counts == {"s1": 42, "s2": 0}
        assert root_count == 42

    def test_missing_estimated_size(self):
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={"100": {}},
        )
        compiled_map = {"s1": 100}
        counts, root_count = extract_step_counts(strategy_info, compiled_map)
        assert counts == {"s1": None}
        assert root_count is None

    def test_no_steps(self):
        strategy_info = _make_strategy_details(root_step_id=100, steps={})
        compiled_map = {"s1": 100}
        counts, root_count = extract_step_counts(strategy_info, compiled_map)
        assert counts == {}
        assert root_count is None

    def test_non_int_wdk_id_skipped(self):
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "abc": {"estimatedSize": 10},
                "100": {"estimatedSize": 5},
            },
        )
        compiled_map = {"s1": 100}
        counts, _root_count = extract_step_counts(strategy_info, compiled_map)
        assert counts == {"s1": 5}

    def test_zero_counts_detected(self):
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "100": {"estimatedSize": 10},
                "200": {"estimatedSize": 0},
                "300": {"estimatedSize": 0},
            },
        )
        compiled_map = {"s1": 100, "s2": 200, "s3": 300}
        counts, _ = extract_step_counts(strategy_info, compiled_map)
        zeros = sorted([sid for sid, c in counts.items() if c == 0])
        assert zeros == ["s2", "s3"]


# ---------------------------------------------------------------------------
# get_estimated_size
# ---------------------------------------------------------------------------


class TestGetResultCount:
    async def test_from_strategy_payload(self):
        api = FakeCountAPI(
            get_strategy_response=_make_strategy_details(
                steps={"42": {"estimatedSize": 100}},
            ),
        )
        result = await get_estimated_size(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result == StepCountResult(step_id=42, count=100)

    async def test_fallback_to_step_count(self):
        api = FakeCountAPI(
            get_strategy_response=_make_strategy_details(steps={}),
            step_count=77,
        )
        result = await get_estimated_size(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result == StepCountResult(step_id=42, count=77)

    async def test_no_strategy_id(self):
        api = FakeCountAPI(step_count=55)
        result = await get_estimated_size(api, wdk_step_id=10)
        assert result == StepCountResult(step_id=10, count=55)

    async def test_estimated_size_none_falls_back(self):
        api = FakeCountAPI(
            get_strategy_response=_make_strategy_details(
                steps={"42": {"estimatedSize": None}},
            ),
            step_count=33,
        )
        result = await get_estimated_size(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result.count == 33
