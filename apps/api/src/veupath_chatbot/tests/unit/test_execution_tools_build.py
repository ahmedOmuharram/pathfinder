"""Unit tests for execution tools build & result-count paths.

Covers edge cases in:
- resolve_root_step (root_count attribute on errors, graph.get_step returning None)
- create_strategy_ast (validation failure, description passthrough)
- extract_step_counts (empty steps, non-int estimatedSize variants, ID mapping)
- create_or_update_wdk_strategy (create returns None ID, update sets name)
- get_estimated_size (step in strategy but estimatedSize is None, non-dict steps)

These tests complement test_strategy_build_service.py by covering scenarios
not present there.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import CompilationResult
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKDatasetConfig,
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import StrategyCompilationError, WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.build import (
    RootResolutionError,
    StepCountResult,
    create_or_update_wdk_strategy,
    create_strategy_ast,
    extract_step_counts,
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
    return WDKStrategyDetails.model_validate({
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
    })


class _FakeBuildAPI:
    """Minimal fake satisfying StrategyBuildAPI."""

    def __init__(
        self,
        *,
        create_step_response: WDKIdentifier | None = None,
        create_strategy_response: WDKIdentifier | None = None,
        update_strategy_error: Exception | None = None,
        get_strategy_response: WDKStrategyDetails | None = None,
        step_count: int = 50,
    ) -> None:
        self._create_step_response = create_step_response or WDKIdentifier(id=100)
        self._create_strategy_response = create_strategy_response or WDKIdentifier(id=999)
        self._update_strategy_error = update_strategy_error
        self._get_strategy_response = get_strategy_response or _make_strategy_details()
        self._step_count = step_count
        self.client = _FakeClient()
        self.created_strategies: list[dict] = []
        self.updated_strategies: list[dict] = []
        self.step_count_calls: list[int] = []

    async def create_step(
        self,
        spec: NewStepSpec,
        record_type: str,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        return self._create_step_response

    async def create_combined_step(  # noqa: PLR0913
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        *,
        spec_overrides: PatchStepSpec | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        return WDKIdentifier(id=200)

    async def create_transform_step(
        self,
        spec: NewStepSpec,
        input_step_id: int,
        record_type: str = "transcript",
        *,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        return WDKIdentifier(id=300)

    async def create_dataset(self, config: WDKDatasetConfig, user_id: str | None = None) -> int:
        return 1

    async def set_step_filter(
        self, step_id: int, filter_name: str, value: object, *, disabled: bool = False
    ) -> object:
        return None

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject:
        return {}

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> object:
        return None

    async def create_strategy(
        self,
        step_tree: object,
        name: str,
        description: str | None = None,
    ) -> WDKIdentifier:
        self.created_strategies.append(
            {"name": name, "description": description, "step_tree": step_tree}
        )
        return self._create_strategy_response

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: object | None = None,
        name: str | None = None,
    ) -> WDKIdentifier:
        if self._update_strategy_error:
            raise self._update_strategy_error
        self.updated_strategies.append(
            {"strategy_id": strategy_id, "name": name, "step_tree": step_tree}
        )
        return WDKIdentifier(id=strategy_id)

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        return self._get_strategy_response

    async def get_step_count(self, step_id: int) -> int:
        self.step_count_calls.append(step_id)
        return self._step_count


class _FakeClient:
    async def get_search_details(
        self, record_type: str, search_name: str, expand_params: bool = False
    ) -> JSONObject:
        return {"searchData": {"parameters": []}}

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        expand_params: bool = False,
    ) -> JSONObject:
        return {"searchData": {"parameters": []}}

    async def get_record_types(self) -> list:
        return []

    async def get_searches(self, record_type: str) -> list:
        return []


# ---------------------------------------------------------------------------
# resolve_root_step — root_count attribute on exceptions
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
# create_strategy_ast — validation failures and edge cases
# ---------------------------------------------------------------------------


class TestCreateStrategyASTEdgeCases:
    def test_description_passed_through(self):
        graph = _graph()
        step = _step()
        ast = create_strategy_ast(graph, step, "Name", "My description")
        assert ast.description == "My description"

    def test_none_name_and_none_graph_name(self):
        """Both strategy_name and graph.name are None => AST.name is None."""
        graph = _graph(name="")
        # StrategyGraph stores whatever name is passed.
        graph.name = ""
        step = _step()
        # graph.name is "" which is falsy, strategy_name is None
        ast = create_strategy_ast(graph, step, None, None)
        # Fallback: name = strategy_name or graph.name = None or "" = ""
        assert ast.name == ""

    def test_uses_graph_record_type(self):
        """Record type comes from graph.record_type."""
        graph = _graph(record_type="transcript")
        step = _step()
        ast = create_strategy_ast(graph, step, None, None)
        assert ast.record_type == "transcript"

    def test_non_plan_step_dict_raises_type_error(self):
        """Passing a dict (not PlanStepNode) raises StrategyCompilationError."""
        graph = _graph()
        with pytest.raises(StrategyCompilationError, match="PlanStepNode"):
            create_strategy_ast(graph, {"search_name": "x"}, None, None)

    def test_non_plan_step_int_raises_type_error(self):
        """Passing an int raises StrategyCompilationError with the type name."""
        graph = _graph()
        with pytest.raises(StrategyCompilationError, match="int"):
            create_strategy_ast(graph, 42, None, None)

    def test_no_record_type_raises(self):
        """graph has no record_type."""
        graph = _graph(record_type=None)
        step = _step()
        with pytest.raises(StrategyCompilationError, match="Record type"):
            create_strategy_ast(graph, step, None, None)


# ---------------------------------------------------------------------------
# extract_step_counts — empty / non-integer estimatedSize / mapping
# ---------------------------------------------------------------------------


class TestExtractStepCountsEdgeCases:
    def test_empty_steps_dict_returns_empty(self):
        info = _make_strategy_details(root_step_id=1, steps={})
        counts, root = extract_step_counts(info, {"s1": 1})
        assert counts == {}
        assert root is None

    def test_none_estimated_size_becomes_none(self):
        info = _make_strategy_details(
            root_step_id=10,
            steps={"10": {"estimatedSize": None}},
        )
        counts, _root = extract_step_counts(info, {"local1": 10})
        assert counts == {"local1": None}

    def test_wdk_to_local_mapping_correct(self):
        """Multiple local steps mapped to different WDK IDs."""
        info = _make_strategy_details(
            root_step_id=500,
            steps={
                "500": {"estimatedSize": 10},
                "600": {"estimatedSize": 20},
                "700": {"estimatedSize": 30},
            },
        )
        compiled_map = {"alpha": 500, "beta": 600, "gamma": 700}
        counts, root = extract_step_counts(info, compiled_map)
        assert counts == {"alpha": 10, "beta": 20, "gamma": 30}
        assert root == 10

    def test_unmapped_wdk_id_ignored(self):
        """WDK step IDs not in compiled_map are silently ignored."""
        info = _make_strategy_details(
            root_step_id=1,
            steps={
                "1": {"estimatedSize": 5},
                "999": {"estimatedSize": 99},
            },
        )
        counts, root = extract_step_counts(info, {"local": 1})
        assert counts == {"local": 5}
        assert root == 5

    def test_root_step_id_maps_to_local_for_root_count(self):
        """root_count is read from the local step mapped to rootStepId."""
        info = _make_strategy_details(
            root_step_id=200,
            steps={
                "100": {"estimatedSize": 5},
                "200": {"estimatedSize": 42},
            },
        )
        compiled_map = {"leaf": 100, "root_local": 200}
        _counts, root = extract_step_counts(info, compiled_map)
        assert root == 42


# ---------------------------------------------------------------------------
# create_or_update_wdk_strategy — edge cases
# ---------------------------------------------------------------------------


class TestCreateOrUpdateEdgeCases:
    async def test_update_preserves_existing_id(self):
        """Successful update returns the existing strategy ID."""
        api = _FakeBuildAPI()
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(record_type="gene", root=_step(), name="Keep")
        result = await create_or_update_wdk_strategy(api, compilation, strategy, 42)
        assert result == 42
        assert api.updated_strategies[0]["strategy_id"] == 42

    async def test_update_sends_name(self):
        """Update sends the strategy name to the API."""
        api = _FakeBuildAPI()
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(record_type="gene", root=_step(), name="Named")
        await create_or_update_wdk_strategy(api, compilation, strategy, 1)
        assert api.updated_strategies[0]["name"] == "Named"

    async def test_update_uses_untitled_when_name_is_none(self):
        """When strategy.name is None, the fallback 'Untitled Strategy' is used."""
        api = _FakeBuildAPI()
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(record_type="gene", root=_step(), name=None)
        await create_or_update_wdk_strategy(api, compilation, strategy, 1)
        assert api.updated_strategies[0]["name"] == "Untitled Strategy"

    async def test_create_sends_description(self):
        """Create passes description to the API."""
        api = _FakeBuildAPI()
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(
            record_type="gene", root=_step(), name="S", description="Desc"
        )
        await create_or_update_wdk_strategy(api, compilation, strategy, None)
        assert api.created_strategies[0]["description"] == "Desc"

    async def test_create_uses_untitled_when_name_is_none(self):
        """Create fallback name is 'Untitled Strategy'."""
        api = _FakeBuildAPI()
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(record_type="gene", root=_step(), name=None)
        await create_or_update_wdk_strategy(api, compilation, strategy, None)
        assert api.created_strategies[0]["name"] == "Untitled Strategy"

    async def test_update_failure_triggers_create(self):
        """After update fails, create is called and its ID is returned."""
        api = _FakeBuildAPI(
            update_strategy_error=WDKError(detail="gone"),
            create_strategy_response=WDKIdentifier(id=777),
        )
        compilation = CompilationResult(
            steps=[], step_tree=WDKStepTree(step_id=1), root_step_id=1
        )
        strategy = StrategyAST(record_type="gene", root=_step(), name="Fallback")
        result = await create_or_update_wdk_strategy(api, compilation, strategy, 99)
        assert result == 777
        assert len(api.created_strategies) == 1
        assert api.created_strategies[0]["name"] == "Fallback"


# ---------------------------------------------------------------------------
# get_estimated_size — edge cases
# ---------------------------------------------------------------------------


class TestGetResultCountEdgeCases:
    async def test_strategy_step_has_none_estimated_size_falls_back(self):
        """estimatedSize is present but None => falls back to get_step_count."""
        api = _FakeBuildAPI(
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
        api = _FakeBuildAPI(
            get_strategy_response=_make_strategy_details(steps={}),
            step_count=12,
        )
        result = await get_estimated_size(api, wdk_step_id=7, wdk_strategy_id=1)
        assert result.count == 12

    async def test_no_strategy_id_calls_step_count_directly(self):
        """Without wdk_strategy_id, get_step_count is called directly."""
        api = _FakeBuildAPI(step_count=99)
        result = await get_estimated_size(api, wdk_step_id=42)
        assert result == StepCountResult(step_id=42, count=99)
        assert 42 in api.step_count_calls

    async def test_step_not_in_strategy_steps_falls_back(self):
        """Step ID is not in strategy.steps dict => falls back."""
        api = _FakeBuildAPI(
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
        api = _FakeBuildAPI(
            get_strategy_response=_make_strategy_details(
                steps={"3": {"estimatedSize": 0}},
            ),
            step_count=999,
        )
        result = await get_estimated_size(api, wdk_step_id=3, wdk_strategy_id=1)
        assert result.count == 0
