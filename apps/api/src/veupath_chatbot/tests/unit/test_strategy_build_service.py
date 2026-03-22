"""Tests for the strategy build service (services/strategies/build.py).

Covers: root resolution, AST creation, create-or-update, step count
extraction, full build orchestration, and result count lookup.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StepTreeNode, StrategyAST
from veupath_chatbot.domain.strategy.compile import CompilationResult
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKSearchResponse,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import StrategyCompilationError, WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.searches import resolve_record_type_from_steps
from veupath_chatbot.services.strategies.build import (
    BuildOptions,
    BuildResult,
    RootResolutionError,
    StepCountResult,
    build_strategy,
    create_or_update_wdk_strategy,
    create_strategy_ast,
    extract_step_counts,
    get_result_count,
    resolve_root_step,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeBuildAPI:
    """Fake API satisfying StrategyBuildAPI for testing."""

    def __init__(
        self,
        *,
        create_step_response: WDKIdentifier | None = None,
        create_strategy_response: WDKIdentifier | None = None,
        update_strategy_error: Exception | None = None,
        get_strategy_response: WDKStrategyDetails | None = None,
        step_count: int = 42,
    ) -> None:
        self._create_step_response = create_step_response or WDKIdentifier(id=100)
        self._create_strategy_response = create_strategy_response or WDKIdentifier(id=999)
        self._update_strategy_error = update_strategy_error
        self._get_strategy_response = get_strategy_response or _make_strategy_details()
        self._step_count = step_count
        self.client = FakeCompilerClient()
        self.created_strategies: list[dict] = []
        self.updated_strategies: list[dict] = []

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> WDKIdentifier:
        return self._create_step_response

    async def create_combined_step(
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> WDKIdentifier:
        return WDKIdentifier(id=200)

    async def create_transform_step(
        self,
        input_step_id: int,
        transform_name: str,
        parameters: JSONObject,
        record_type: str = "transcript",
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> WDKIdentifier:
        return WDKIdentifier(id=300)

    async def create_dataset(self, ids: list[str]) -> int:
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
        self.created_strategies.append({"name": name, "description": description})
        return self._create_strategy_response

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: object | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails:
        if self._update_strategy_error:
            raise self._update_strategy_error
        self.updated_strategies.append({"strategy_id": strategy_id, "name": name})
        return self._get_strategy_response

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        return self._get_strategy_response

    async def get_step_count(self, step_id: int) -> int:
        return self._step_count


class FakeCompilerClient:
    """Fake compiler client for StrategyCompilerAPI.client."""

    def _default_response(self) -> WDKSearchResponse:
        return WDKSearchResponse.model_validate({
            "searchData": {"urlSegment": "FakeSearch", "parameters": []},
            "validation": {"level": "DISPLAYABLE", "isValid": True},
        })

    async def get_search_details(
        self, record_type: str, search_name: str, expand_params: bool = False
    ) -> WDKSearchResponse:
        return self._default_response()

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        expand_params: bool = False,
    ) -> WDKSearchResponse:
        return self._default_response()

    async def get_record_types(self) -> list:
        return []

    async def get_searches(self, record_type: str) -> list:
        return []


class FakeSite:
    """Fake site info satisfying SiteInfoLike."""

    def strategy_url(self, strategy_id: int, root_step_id: int | None = None) -> str:
        if root_step_id is not None:
            return f"https://example.com/strategies/{strategy_id}/{root_step_id}"
        return f"https://example.com/strategies/{strategy_id}"


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
# create_strategy_ast
# ---------------------------------------------------------------------------


class TestCreateStrategyAST:
    def test_valid_creation(self):
        graph = _make_graph()
        step = _make_step()
        result = create_strategy_ast(graph, step, "My Strategy", "desc")
        assert isinstance(result, StrategyAST)
        assert result.name == "My Strategy"
        assert result.record_type == "gene"

    def test_uses_graph_record_type(self):
        graph = _make_graph(record_type="transcript")
        step = _make_step()
        result = create_strategy_ast(graph, step, None, None)
        assert result.record_type == "transcript"

    def test_missing_record_type_raises(self):
        graph = _make_graph(record_type=None)
        step = _make_step()
        with pytest.raises(StrategyCompilationError, match="Record type"):
            create_strategy_ast(graph, step, None, None)

    def test_wrong_type_raises(self):
        graph = _make_graph()
        with pytest.raises(StrategyCompilationError, match="PlanStepNode"):
            create_strategy_ast(graph, "not a step", None, None)

    def test_name_falls_back_to_graph_name(self):
        graph = _make_graph(name="Graph Name")
        step = _make_step()
        result = create_strategy_ast(graph, step, None, None)
        assert result.name == "Graph Name"


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
    return WDKStrategyDetails.model_validate({
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
    })


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
# create_or_update_wdk_strategy
# ---------------------------------------------------------------------------


class TestCreateOrUpdateWdkStrategy:
    async def test_create_new(self):
        api = FakeBuildAPI(create_strategy_response=WDKIdentifier(id=555))
        compilation = CompilationResult(
            steps=[],
            step_tree=StepTreeNode(step_id=1),
            root_step_id=1,
        )
        strategy = StrategyAST(record_type="gene", root=_make_step(), name="Test")
        result = await create_or_update_wdk_strategy(api, compilation, strategy, None)
        assert result == 555
        assert len(api.created_strategies) == 1

    async def test_update_existing(self):
        api = FakeBuildAPI()
        compilation = CompilationResult(
            steps=[],
            step_tree=StepTreeNode(step_id=1),
            root_step_id=1,
        )
        strategy = StrategyAST(record_type="gene", root=_make_step(), name="Test")
        result = await create_or_update_wdk_strategy(api, compilation, strategy, 777)
        assert result == 777
        assert len(api.updated_strategies) == 1
        assert len(api.created_strategies) == 0

    async def test_update_fails_falls_back_to_create(self):
        api = FakeBuildAPI(
            update_strategy_error=WDKError(detail="404 Not Found"),
            create_strategy_response=WDKIdentifier(id=888),
        )
        compilation = CompilationResult(
            steps=[],
            step_tree=StepTreeNode(step_id=1),
            root_step_id=1,
        )
        strategy = StrategyAST(record_type="gene", root=_make_step(), name="Test")
        result = await create_or_update_wdk_strategy(api, compilation, strategy, 777)
        assert result == 888
        assert len(api.created_strategies) == 1


# ---------------------------------------------------------------------------
# get_result_count
# ---------------------------------------------------------------------------


class TestGetResultCount:
    async def test_from_strategy_payload(self):
        api = FakeBuildAPI(
            get_strategy_response=_make_strategy_details(
                steps={"42": {"estimatedSize": 100}},
            ),
        )
        result = await get_result_count(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result == StepCountResult(step_id=42, count=100)

    async def test_fallback_to_step_count(self):
        api = FakeBuildAPI(
            get_strategy_response=_make_strategy_details(steps={}),
            step_count=77,
        )
        result = await get_result_count(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result == StepCountResult(step_id=42, count=77)

    async def test_no_strategy_id(self):
        api = FakeBuildAPI(step_count=55)
        result = await get_result_count(api, wdk_step_id=10)
        assert result == StepCountResult(step_id=10, count=55)

    async def test_estimated_size_none_falls_back(self):
        api = FakeBuildAPI(
            get_strategy_response=_make_strategy_details(
                steps={"42": {"estimatedSize": None}},
            ),
            step_count=33,
        )
        result = await get_result_count(api, wdk_step_id=42, wdk_strategy_id=1)
        assert result.count == 33


# ---------------------------------------------------------------------------
# Full build_strategy orchestration
# ---------------------------------------------------------------------------


class TestBuildStrategy:
    async def test_full_build_new_strategy(self):
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)

        api = FakeBuildAPI(
            create_strategy_response=WDKIdentifier(id=999),
            get_strategy_response=_make_strategy_details(
                root_step_id=100,
                steps={"100": {"estimatedSize": 42}},
            ),
        )
        site = FakeSite()

        result = await build_strategy(
            graph=graph,
            api=api,
            site=site,
            site_id="plasmodb",
            options=BuildOptions(strategy_name="My Strategy"),
        )

        assert isinstance(result, BuildResult)
        assert result.wdk_strategy_id == 999
        assert result.wdk_url is not None
        assert "999" in result.wdk_url
        assert graph.wdk_strategy_id == 999
        assert graph.current_strategy is not None

    async def test_update_existing_strategy(self):
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)
        graph.wdk_strategy_id = 500

        # Pre-set a strategy on the graph that includes our step.
        ast = StrategyAST(record_type="gene", root=step, name="Existing")
        graph.current_strategy = ast

        api = FakeBuildAPI(
            get_strategy_response=_make_strategy_details(
                root_step_id=100,
                steps={"100": {"estimatedSize": 10}},
            ),
        )
        site = FakeSite()

        result = await build_strategy(
            graph=graph,
            api=api,
            site=site,
            site_id="plasmodb",
        )

        assert result.wdk_strategy_id == 500
        assert len(api.updated_strategies) == 1

    async def test_build_with_no_roots_raises(self):
        graph = _make_graph()
        api = FakeBuildAPI()
        site = FakeSite()

        with pytest.raises(RootResolutionError, match="No steps"):
            await build_strategy(
                graph=graph,
                api=api,
                site=site,
                site_id="plasmodb",
            )

    async def test_build_with_multiple_roots_raises(self):
        graph = _make_graph()
        graph.add_step(_make_step("s1"))
        graph.add_step(_make_step("s2", search_name="GenesByLocation"))

        api = FakeBuildAPI()
        site = FakeSite()

        with pytest.raises(RootResolutionError, match="subtree roots"):
            await build_strategy(
                graph=graph,
                api=api,
                site=site,
                site_id="plasmodb",
            )

    async def test_strategy_name_updates_graph(self):
        graph = _make_graph(name="Old Name")
        step = _make_step("s1")
        graph.add_step(step)

        api = FakeBuildAPI(
            create_strategy_response=WDKIdentifier(id=111),
            get_strategy_response=_make_strategy_details(steps={}),
        )
        site = FakeSite()

        await build_strategy(
            graph=graph,
            api=api,
            site=site,
            site_id="plasmodb",
            options=BuildOptions(strategy_name="New Name"),
        )

        assert graph.name == "New Name"

    async def test_zero_steps_detected(self):
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)

        api = FakeBuildAPI(
            create_strategy_response=WDKIdentifier(id=111),
            get_strategy_response=_make_strategy_details(
                root_step_id=100,
                steps={"100": {"estimatedSize": 0}},
            ),
        )
        site = FakeSite()

        result = await build_strategy(
            graph=graph,
            api=api,
            site=site,
            site_id="plasmodb",
        )

        assert len(result.zero_step_ids) > 0
