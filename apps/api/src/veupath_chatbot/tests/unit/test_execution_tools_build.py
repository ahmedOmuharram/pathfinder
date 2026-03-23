"""Unit tests for execution tools build & result-count paths.

Covers edge cases in:
- resolve_root_step (root_count attribute on errors, graph.get_step returning None)
- get_estimated_size (step in strategy but estimatedSize is None, non-dict steps)

These tests complement test_strategy_build_service.py by covering scenarios
not present there.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKStrategyDetails,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.build import (
    RootResolutionError,
    StepCountResult,
    get_estimated_size,
    resolve_root_step,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _graph(
    *,
    site_id: str = "plasmodb",
    name: str = "G",
    record_type: str | None = "gene",
) -> StrategyGraph:
    g = StrategyGraph("g-test", name, site_id)
    g.record_type = record_type
    return g


def _step(
    step_id: str = "s1",
    search_name: str = "GenesByTaxon",
    parameters: JSONObject | None = None,
) -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        parameters=parameters or {},
        id=step_id,
    )


def _make_strategy_details(
    root_step_id: int = 100,
    steps: dict[str, dict[str, object]] | None = None,
) -> WDKStrategyDetails:
    """Build a WDKStrategyDetails from step data for tests."""
    raw_steps = steps or {}
    return WDKStrategyDetails.model_validate(
        {
            "strategyId": 1,
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


class _FakeCountAPI:
    """Minimal fake satisfying StepCountAPI."""

    def __init__(
        self,
        *,
        get_strategy_response: WDKStrategyDetails | None = None,
        step_count: int = 50,
    ) -> None:
        self._get_strategy_response = get_strategy_response or _make_strategy_details()
        self._step_count = step_count
        self.step_count_calls: list[int] = []

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        return self._get_strategy_response

    async def get_step_count(self, step_id: int) -> int:
        self.step_count_calls.append(step_id)
        return self._step_count


# ---------------------------------------------------------------------------
# resolve_root_step -- root_count attribute on exceptions
# ---------------------------------------------------------------------------


class TestResolveRootStepAttributes:
    """Verify RootResolutionError.root_count is set correctly."""

    def test_zero_roots_sets_root_count_zero(self):
        graph = _graph()
        with pytest.raises(RootResolutionError) as exc_info:
            resolve_root_step(graph, None)
        assert exc_info.value.root_count == 0

    def test_multiple_roots_sets_root_count(self):
        graph = _graph()
        graph.add_step(_step("a"))
        graph.add_step(_step("b", search_name="GenesByLocation"))
        graph.add_step(_step("c", search_name="GenesByProduct"))
        with pytest.raises(RootResolutionError) as exc_info:
            resolve_root_step(graph, None)
        assert exc_info.value.root_count == 3

    def test_explicit_root_not_found_root_count_defaults_zero(self):
        """Explicit-root-not-found uses default root_count=0."""
        graph = _graph()
        graph.add_step(_step("s1"))
        with pytest.raises(RootResolutionError) as exc_info:
            resolve_root_step(graph, "nonexistent_id")
        assert exc_info.value.root_count == 0

    def test_single_root_returns_correct_step(self):
        """Single root auto-resolves and returns the exact step object."""
        graph = _graph()
        step = _step("only")
        graph.add_step(step)
        result = resolve_root_step(graph, None)
        assert result is step

    def test_explicit_root_returns_exact_object(self):
        """Explicit root_step_id returns the exact step from graph."""
        graph = _graph()
        step = _step("target")
        graph.add_step(step)
        graph.add_step(_step("other", search_name="GenesByLocation"))
        # With 2 roots, auto-resolve would fail, but explicit works.
        result = resolve_root_step(graph, "target")
        assert result is step


# ---------------------------------------------------------------------------
# get_estimated_size -- edge cases
# ---------------------------------------------------------------------------


class TestGetResultCountEdgeCases:
    async def test_strategy_step_has_none_estimated_size_falls_back(self):
        """estimatedSize is present but None => falls back to get_step_count."""
        api = _FakeCountAPI(
            get_strategy_response=_make_strategy_details(
                steps={"5": {"estimatedSize": None}},
            ),
            step_count=88,
        )
        result = await get_estimated_size(api, wdk_step_id=5, wdk_strategy_id=1)
        assert result == StepCountResult(step_id=5, count=88)
        assert 5 in api.step_count_calls

    async def test_empty_steps_falls_back(self):
        """No matching step in steps dict => falls back."""
        api = _FakeCountAPI(
            get_strategy_response=_make_strategy_details(steps={}),
            step_count=12,
        )
        result = await get_estimated_size(api, wdk_step_id=7, wdk_strategy_id=1)
        assert result.count == 12

    async def test_no_strategy_id_calls_step_count_directly(self):
        """Without wdk_strategy_id, get_step_count is called directly."""
        api = _FakeCountAPI(step_count=99)
        result = await get_estimated_size(api, wdk_step_id=42)
        assert result == StepCountResult(step_id=42, count=99)
        assert 42 in api.step_count_calls

    async def test_step_not_in_strategy_steps_falls_back(self):
        """Step ID is not in strategy.steps dict => falls back."""
        api = _FakeCountAPI(
            get_strategy_response=_make_strategy_details(
                steps={"100": {"estimatedSize": 50}},
            ),
            step_count=60,
        )
        # wdk_step_id=200 is not in the steps dict
        result = await get_estimated_size(api, wdk_step_id=200, wdk_strategy_id=1)
        assert result.count == 60
        assert 200 in api.step_count_calls

    async def test_estimated_size_zero_returned(self):
        """estimatedSize=0 is a valid int and should be returned."""
        api = _FakeCountAPI(
            get_strategy_response=_make_strategy_details(
                steps={"3": {"estimatedSize": 0}},
            ),
            step_count=999,
        )
        result = await get_estimated_size(api, wdk_step_id=3, wdk_strategy_id=1)
        assert result.count == 0
