"""Tests for the strategy sync service (services/strategies/sync.py).

Covers: step tree construction, tree comparison, count/validation extraction,
create-or-update logic, decoration application, graph state mutation, and
the full sync orchestration flow.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
)
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import StrategyCompilationError, WDKError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.strategies.build import RootResolutionError
from veupath_chatbot.services.strategies.sync import (
    SyncResult,
    _extract_counts_and_validations,
    _trees_equal,
    build_step_tree_from_graph,
    sync_strategy,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSyncAPI:
    """Fake API satisfying StrategySyncAPI for testing."""

    def __init__(
        self,
        *,
        create_strategy_response: WDKIdentifier | None = None,
        update_strategy_error: Exception | None = None,
        get_strategy_response: WDKStrategyDetails | None = None,
    ) -> None:
        self._create_strategy_response = create_strategy_response or WDKIdentifier(
            id=999
        )
        self._update_strategy_error = update_strategy_error
        self._get_strategy_response = get_strategy_response or _make_strategy_details()
        self.created_strategies: list[dict[str, object]] = []
        self.updated_strategies: list[dict[str, object]] = []
        self.applied_filters: list[dict[str, object]] = []
        self.run_analyses: list[dict[str, object]] = []
        self.run_reports: list[dict[str, object]] = []

    async def create_strategy(
        self,
        step_tree: WDKStepTree,
        name: str,
        description: str | None = None,
        *,
        is_public: bool = False,
        is_saved: bool = False,
    ) -> WDKIdentifier:
        self.created_strategies.append({"name": name, "description": description})
        return self._create_strategy_response

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: WDKStepTree | None = None,
        name: str | None = None,
    ) -> WDKStrategyDetails:
        if self._update_strategy_error:
            raise self._update_strategy_error
        self.updated_strategies.append({"strategy_id": strategy_id, "name": name})
        return self._get_strategy_response

    async def get_strategy(self, strategy_id: int) -> WDKStrategyDetails:
        return self._get_strategy_response

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JSONValue,
        *,
        disabled: bool = False,
    ) -> JSONValue:
        self.applied_filters.append(
            {
                "step_id": step_id,
                "filter_name": filter_name,
                "value": value,
                "disabled": disabled,
            }
        )
        return None

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject:
        self.run_analyses.append(
            {
                "step_id": step_id,
                "analysis_type": analysis_type,
                "parameters": parameters,
                "custom_name": custom_name,
            }
        )
        return {}

    async def run_step_report(
        self,
        step_id: int,
        report_name: str,
        config: JSONObject | None = None,
    ) -> JSONValue:
        self.run_reports.append(
            {
                "step_id": step_id,
                "report_name": report_name,
                "config": config,
            }
        )
        return None


class FakeSite:
    """Fake site info satisfying SiteInfoLike."""

    def strategy_url(self, strategy_id: int, root_step_id: int | None = None) -> str:
        if root_step_id is not None:
            return f"https://example.com/strategies/{strategy_id}/{root_step_id}"
        return f"https://example.com/strategies/{strategy_id}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    filters: list[StepFilter] | None = None,
    analyses: list[StepAnalysis] | None = None,
    reports: list[StepReport] | None = None,
) -> PlanStepNode:
    return PlanStepNode(
        search_name=search_name,
        parameters=parameters or {},
        id=step_id,
        filters=filters or [],
        analyses=analyses or [],
        reports=reports or [],
    )


def _make_combine_step(
    step_id: str = "combine_1",
    primary: PlanStepNode | None = None,
    secondary: PlanStepNode | None = None,
) -> PlanStepNode:
    return PlanStepNode(
        search_name="__combine__",
        parameters={},
        id=step_id,
        primary_input=primary or _make_step("left"),
        secondary_input=secondary or _make_step("right"),
        operator=CombineOp.INTERSECT,
    )


def _make_strategy_details(
    root_step_id: int = 100,
    steps: dict[str, dict[str, object]] | None = None,
    strategy_id: int = 999,
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


def _graph_with_single_step(
    step_id: str = "step_1",
    wdk_step_id: int = 100,
    wdk_strategy_id: int | None = None,
) -> tuple[StrategyGraph, PlanStepNode]:
    """Create a graph with a single step that has a WDK ID assigned."""
    graph = _make_graph()
    step = _make_step(step_id=step_id)
    graph.add_step(step)
    graph.wdk_step_ids[step_id] = wdk_step_id
    graph.wdk_strategy_id = wdk_strategy_id
    return graph, step


# ---------------------------------------------------------------------------
# build_step_tree_from_graph
# ---------------------------------------------------------------------------


class TestBuildStepTreeFromGraph:
    def test_single_leaf_step(self) -> None:
        step = _make_step("s1")
        wdk_ids = {"s1": 100}
        tree = build_step_tree_from_graph(step, wdk_ids)
        assert tree.step_id == 100
        assert tree.primary_input is None
        assert tree.secondary_input is None

    def test_combine_step_with_two_inputs(self) -> None:
        left = _make_step("left")
        right = _make_step("right")
        root = _make_combine_step("root", primary=left, secondary=right)
        wdk_ids = {"left": 10, "right": 20, "root": 30}
        tree = build_step_tree_from_graph(root, wdk_ids)
        assert tree.step_id == 30
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 10
        assert tree.secondary_input is not None
        assert tree.secondary_input.step_id == 20

    def test_missing_wdk_id_raises_compilation_error(self) -> None:
        step = _make_step("s1")
        wdk_ids: dict[str, int] = {}
        with pytest.raises(StrategyCompilationError, match="no WDK step ID"):
            build_step_tree_from_graph(step, wdk_ids)

    def test_missing_input_wdk_id_raises_compilation_error(self) -> None:
        left = _make_step("left")
        right = _make_step("right")
        root = _make_combine_step("root", primary=left, secondary=right)
        # Missing WDK ID for "left"
        wdk_ids = {"right": 20, "root": 30}
        with pytest.raises(StrategyCompilationError, match="left"):
            build_step_tree_from_graph(root, wdk_ids)

    def test_deeply_nested_tree(self) -> None:
        """Build tree for A -> B -> C (chain of transforms)."""
        leaf = _make_step("leaf", search_name="GenesByTaxon")
        mid = PlanStepNode(
            search_name="GenesByOrthologs",
            parameters={},
            id="mid",
            primary_input=leaf,
        )
        root = PlanStepNode(
            search_name="GenesByWeightFilter",
            parameters={},
            id="root",
            primary_input=mid,
        )
        wdk_ids = {"leaf": 1, "mid": 2, "root": 3}
        tree = build_step_tree_from_graph(root, wdk_ids)
        assert tree.step_id == 3
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 2
        assert tree.primary_input.primary_input is not None
        assert tree.primary_input.primary_input.step_id == 1


# ---------------------------------------------------------------------------
# _trees_equal
# ---------------------------------------------------------------------------


class TestTreesEqual:
    def test_both_none(self) -> None:
        assert _trees_equal(None, None) is True

    def test_one_none(self) -> None:
        tree = WDKStepTree(step_id=1)
        assert _trees_equal(tree, None) is False
        assert _trees_equal(None, tree) is False

    def test_same_single_node(self) -> None:
        a = WDKStepTree(step_id=1)
        b = WDKStepTree(step_id=1)
        assert _trees_equal(a, b) is True

    def test_different_step_ids(self) -> None:
        a = WDKStepTree(step_id=1)
        b = WDKStepTree(step_id=2)
        assert _trees_equal(a, b) is False

    def test_nested_equal(self) -> None:
        a = WDKStepTree(
            step_id=3,
            primary_input=WDKStepTree(step_id=1),
            secondary_input=WDKStepTree(step_id=2),
        )
        b = WDKStepTree(
            step_id=3,
            primary_input=WDKStepTree(step_id=1),
            secondary_input=WDKStepTree(step_id=2),
        )
        assert _trees_equal(a, b) is True

    def test_nested_different_secondary(self) -> None:
        a = WDKStepTree(
            step_id=3,
            primary_input=WDKStepTree(step_id=1),
            secondary_input=WDKStepTree(step_id=2),
        )
        b = WDKStepTree(
            step_id=3,
            primary_input=WDKStepTree(step_id=1),
            secondary_input=WDKStepTree(step_id=99),
        )
        assert _trees_equal(a, b) is False

    def test_one_has_input_other_doesnt(self) -> None:
        a = WDKStepTree(step_id=1, primary_input=WDKStepTree(step_id=2))
        b = WDKStepTree(step_id=1)
        assert _trees_equal(a, b) is False


# ---------------------------------------------------------------------------
# _extract_counts_and_validations
# ---------------------------------------------------------------------------


class TestExtractCountsAndValidations:
    def test_basic_extraction(self) -> None:
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "100": {"estimatedSize": 42},
                "200": {"estimatedSize": 7},
            },
        )
        wdk_step_ids = {"step_a": 100, "step_b": 200}
        counts, _validations, root_count = _extract_counts_and_validations(
            strategy_info, wdk_step_ids
        )
        assert counts["step_a"] == 42
        assert counts["step_b"] == 7
        assert root_count == 42

    def test_unknown_wdk_ids_ignored(self) -> None:
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "100": {"estimatedSize": 42},
                "999": {"estimatedSize": 99},
            },
        )
        wdk_step_ids = {"step_a": 100}
        counts, _, _ = _extract_counts_and_validations(strategy_info, wdk_step_ids)
        assert "step_a" in counts
        assert len(counts) == 1

    def test_null_estimated_size(self) -> None:
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={"100": {"estimatedSize": None}},
        )
        wdk_step_ids = {"step_a": 100}
        counts, _, root_count = _extract_counts_and_validations(
            strategy_info, wdk_step_ids
        )
        assert counts["step_a"] is None
        assert root_count is None

    def test_validations_extracted(self) -> None:
        strategy_info = _make_strategy_details(
            root_step_id=100,
            steps={
                "100": {
                    "estimatedSize": 10,
                    "validation": {
                        "level": "DISPLAYABLE",
                        "isValid": True,
                    },
                },
            },
        )
        wdk_step_ids = {"step_a": 100}
        _, validations, _ = _extract_counts_and_validations(strategy_info, wdk_step_ids)
        assert "step_a" in validations
        assert validations["step_a"].is_valid is True

    def test_empty_steps_returns_empty(self) -> None:
        strategy_info = _make_strategy_details(root_step_id=100, steps={})
        wdk_step_ids = {"step_a": 100}
        counts, validations, root_count = _extract_counts_and_validations(
            strategy_info, wdk_step_ids
        )
        assert counts == {}
        assert validations == {}
        assert root_count is None


# ---------------------------------------------------------------------------
# sync_strategy — create path
# ---------------------------------------------------------------------------


class TestSyncStrategyCreate:
    @pytest.mark.anyio
    async def test_creates_strategy_when_no_wdk_id(self) -> None:
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI(
            get_strategy_response=_make_strategy_details(
                root_step_id=100,
                steps={"100": {"estimatedSize": 42}},
            ),
        )
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert result.wdk_strategy_id == 999
        assert len(api.created_strategies) == 1
        assert len(api.updated_strategies) == 0
        assert result.root_step_id == 100
        assert result.counts == {"step_1": 42}

    @pytest.mark.anyio
    async def test_graph_state_mutated_after_create(self) -> None:
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

        assert graph.wdk_strategy_id == 999
        assert graph.wdk_step_tree is not None
        assert graph.wdk_step_tree.step_id == 100

    @pytest.mark.anyio
    async def test_wdk_url_generated(self) -> None:
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI(
            get_strategy_response=_make_strategy_details(root_step_id=100),
        )
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert result.wdk_url is not None
        assert "999" in result.wdk_url
        assert "100" in result.wdk_url

    @pytest.mark.anyio
    async def test_strategy_name_override(self) -> None:
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(
            graph=graph,
            api=api,
            site=site,
            site_id="plasmodb",
            strategy_name="Custom Name",
        )

        assert api.created_strategies[0]["name"] == "Custom Name"


# ---------------------------------------------------------------------------
# sync_strategy — update path
# ---------------------------------------------------------------------------


class TestSyncStrategyUpdate:
    @pytest.mark.anyio
    async def test_updates_when_tree_changed(self) -> None:
        graph, _ = _graph_with_single_step(wdk_strategy_id=888)
        # Set a different existing tree so the new one triggers an update.
        graph.wdk_step_tree = WDKStepTree(step_id=999)
        api = FakeSyncAPI()
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert len(api.created_strategies) == 0
        assert len(api.updated_strategies) == 1
        assert api.updated_strategies[0]["strategy_id"] == 888
        assert result.wdk_strategy_id == 888

    @pytest.mark.anyio
    async def test_skips_update_when_tree_unchanged(self) -> None:
        graph, _ = _graph_with_single_step(wdk_strategy_id=888)
        # Set existing tree to match the expected tree.
        graph.wdk_step_tree = WDKStepTree(step_id=100)
        api = FakeSyncAPI()
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert len(api.created_strategies) == 0
        assert len(api.updated_strategies) == 0
        assert result.wdk_strategy_id == 888

    @pytest.mark.anyio
    async def test_falls_back_to_create_on_update_failure(self) -> None:
        graph, _ = _graph_with_single_step(wdk_strategy_id=888)
        graph.wdk_step_tree = WDKStepTree(step_id=999)
        api = FakeSyncAPI(
            update_strategy_error=WDKError("Strategy not found", status=404),
        )
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert len(api.created_strategies) == 1
        assert result.wdk_strategy_id == 999


# ---------------------------------------------------------------------------
# sync_strategy — error paths
# ---------------------------------------------------------------------------


class TestSyncStrategyErrors:
    @pytest.mark.anyio
    async def test_raises_on_empty_graph(self) -> None:
        graph = _make_graph()
        api = FakeSyncAPI()
        site = FakeSite()

        with pytest.raises(RootResolutionError, match="No steps"):
            await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

    @pytest.mark.anyio
    async def test_raises_on_multiple_roots(self) -> None:
        graph = _make_graph()
        step1 = _make_step("s1", search_name="GenesByTaxon")
        step2 = _make_step("s2", search_name="GenesByLocation")
        graph.add_step(step1)
        graph.add_step(step2)
        graph.wdk_step_ids = {"s1": 100, "s2": 200}
        api = FakeSyncAPI()
        site = FakeSite()

        with pytest.raises(RootResolutionError, match="subtree roots"):
            await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

    @pytest.mark.anyio
    async def test_raises_on_missing_wdk_step_id(self) -> None:
        graph = _make_graph()
        step = _make_step("s1")
        graph.add_step(step)
        # No wdk_step_ids set
        api = FakeSyncAPI()
        site = FakeSite()

        with pytest.raises(StrategyCompilationError, match="no WDK step ID"):
            await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")


# ---------------------------------------------------------------------------
# sync_strategy — zero step tracking
# ---------------------------------------------------------------------------


class TestSyncZeroSteps:
    @pytest.mark.anyio
    async def test_zero_steps_tracked(self) -> None:
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI(
            get_strategy_response=_make_strategy_details(
                root_step_id=100,
                steps={"100": {"estimatedSize": 0}},
            ),
        )
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert result.zero_step_ids == ["step_1"]
        assert result.root_count == 0


# ---------------------------------------------------------------------------
# sync_strategy — decorations
# ---------------------------------------------------------------------------


class TestSyncDecorations:
    @pytest.mark.anyio
    async def test_filters_applied(self) -> None:
        graph = _make_graph()
        step = _make_step(
            "s1",
            filters=[StepFilter(name="matched_transcript_filter_array", value="Y")],
        )
        graph.add_step(step)
        graph.wdk_step_ids = {"s1": 100}

        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

        assert len(api.applied_filters) == 1
        assert api.applied_filters[0]["step_id"] == 100
        assert (
            api.applied_filters[0]["filter_name"] == "matched_transcript_filter_array"
        )

    @pytest.mark.anyio
    async def test_analyses_applied(self) -> None:
        graph = _make_graph()
        step = _make_step(
            "s1",
            analyses=[
                StepAnalysis(
                    analysis_type="go-enrichment", parameters={"goAspect": "P"}
                )
            ],
        )
        graph.add_step(step)
        graph.wdk_step_ids = {"s1": 100}

        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

        assert len(api.run_analyses) == 1
        assert api.run_analyses[0]["analysis_type"] == "go-enrichment"

    @pytest.mark.anyio
    async def test_reports_applied(self) -> None:
        graph = _make_graph()
        step = _make_step(
            "s1",
            reports=[StepReport(report_name="tabular", config={"format": "csv"})],
        )
        graph.add_step(step)
        graph.wdk_step_ids = {"s1": 100}

        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

        assert len(api.run_reports) == 1
        assert api.run_reports[0]["report_name"] == "tabular"

    @pytest.mark.anyio
    async def test_no_decorations_skips_apply(self) -> None:
        """When steps have no decorations, apply_step_decorations is not called."""
        graph, _ = _graph_with_single_step()
        api = FakeSyncAPI()
        site = FakeSite()

        await sync_strategy(graph=graph, api=api, site=site, site_id="plasmodb")

        assert len(api.applied_filters) == 0
        assert len(api.run_analyses) == 0
        assert len(api.run_reports) == 0


# ---------------------------------------------------------------------------
# sync_strategy — combine step tree
# ---------------------------------------------------------------------------


class TestSyncCombineTree:
    @pytest.mark.anyio
    async def test_combine_step_tree_built_correctly(self) -> None:
        graph = _make_graph()
        left = _make_step("left")
        right = _make_step("right")
        root = _make_combine_step("root", primary=left, secondary=right)
        graph.add_step(left)
        graph.add_step(right)
        graph.add_step(root)
        graph.wdk_step_ids = {"left": 10, "right": 20, "root": 30}

        api = FakeSyncAPI(
            get_strategy_response=_make_strategy_details(
                root_step_id=30,
                steps={
                    "10": {"estimatedSize": 100},
                    "20": {"estimatedSize": 50},
                    "30": {"estimatedSize": 25},
                },
            ),
        )
        site = FakeSite()

        result = await sync_strategy(
            graph=graph, api=api, site=site, site_id="plasmodb"
        )

        assert result.step_count == 3
        assert result.counts == {"left": 100, "right": 50, "root": 25}
        assert result.root_count == 25
        assert graph.wdk_step_tree is not None
        assert graph.wdk_step_tree.step_id == 30
        assert graph.wdk_step_tree.primary_input is not None
        assert graph.wdk_step_tree.primary_input.step_id == 10
        assert graph.wdk_step_tree.secondary_input is not None
        assert graph.wdk_step_tree.secondary_input.step_id == 20


# ---------------------------------------------------------------------------
# SyncResult dataclass
# ---------------------------------------------------------------------------


class TestSyncResult:
    def test_dataclass_fields(self) -> None:
        result = SyncResult(
            wdk_strategy_id=1,
            wdk_url="https://example.com",
            root_step_id=100,
            counts={"s1": 42},
            root_count=42,
            zero_step_ids=[],
            step_count=1,
        )
        assert result.wdk_strategy_id == 1
        assert result.wdk_url == "https://example.com"
        assert result.root_step_id == 100
        assert result.counts == {"s1": 42}
        assert result.root_count == 42
        assert result.zero_step_ids == []
        assert result.step_count == 1
