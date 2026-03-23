"""Unit tests for services.strategies.wdk_conversion pure functions."""

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearchConfig,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)
from veupath_chatbot.services.strategies.wdk_counts import plan_cache_key


def _wdk_step(step_id: int, search_name: str, params: dict[str, str] | None = None) -> WDKStep:
    return WDKStep(
        id=step_id,
        search_name=search_name,
        search_config=WDKSearchConfig(parameters=params or {}),
    )


def _strategy(
    *,
    record_class_name: str = "gene",
    name: str = "Test Strategy",
    step_tree: WDKStepTree,
    steps: dict[str, WDKStep],
    description: str = "",
    is_saved: bool = False,
) -> WDKStrategyDetails:
    return WDKStrategyDetails(
        strategy_id=1,
        name=name,
        root_step_id=step_tree.step_id,
        record_class_name=record_class_name,
        step_tree=step_tree,
        steps=steps,
        description=description,
        is_saved=is_saved,
    )


# -- plan_cache_key ------------------------------------------------------------


class TestPlanCacheKey:
    def test_deterministic(self) -> None:
        plan = {"recordType": "gene", "root": {"searchName": "S1"}}
        key1 = plan_cache_key("plasmodb", plan)
        key2 = plan_cache_key("plasmodb", plan)
        assert key1 == key2

    def test_different_sites_produce_different_keys(self) -> None:
        plan = {"recordType": "gene"}
        key1 = plan_cache_key("plasmodb", plan)
        key2 = plan_cache_key("toxodb", plan)
        assert key1 != key2

    def test_different_plans_produce_different_keys(self) -> None:
        key1 = plan_cache_key("plasmodb", {"recordType": "gene"})
        key2 = plan_cache_key("plasmodb", {"recordType": "transcript"})
        assert key1 != key2


# -- build_snapshot_from_wdk ---------------------------------------------------


class TestBuildSnapshotFromWdk:
    def test_simple_strategy(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"})},
            name="My Strategy",
            description="Test description",
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.record_type == "gene"
        assert ast.name == "My Strategy"
        assert ast.description == "Test description"
        assert ast.root.search_name == "GenesByTextSearch"
        assert len(ast.get_all_steps()) == 1

    def test_combine_strategy(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByGoTerm"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
            name="Combined",
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "combine"
        assert len(ast.get_all_steps()) == 3

    def test_missing_record_class_name_raises(self) -> None:
        wdk = _strategy(
            record_class_name="",
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "S1")},
        )
        with pytest.raises(DataParsingError, match="recordClassName"):
            build_snapshot_from_wdk(wdk)

    def test_missing_step_in_steps_dict_raises(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=999),
            steps={"1": _wdk_step(1, "S1")},
        )
        with pytest.raises(DataParsingError, match="Step 999 not found"):
            build_snapshot_from_wdk(wdk)

    def test_wdk_step_ids_populated(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=42),
            steps={"42": _wdk_step(42, "GenesByTextSearch")},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.id == "42"
        assert ast.wdk_step_ids is not None
        assert ast.wdk_step_ids["42"] == 42

    def test_estimated_size_on_ast(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="GenesByTextSearch",
                    search_config=WDKSearchConfig(parameters={}),
                    estimated_size=500,
                ),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.step_counts is not None
        assert ast.step_counts["1"] == 500

    def test_missing_name_is_none(self) -> None:
        wdk = _strategy(
            name="",
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "S1")},
        )
        ast = build_snapshot_from_wdk(wdk)
        # Empty string is treated as None via `or None`
        assert ast.name is None

    def test_leaf_step_has_correct_kind(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text_expression": "kinase"})},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "search"
        assert ast.root.primary_input is None
        assert ast.root.secondary_input is None

    def test_transform_step_has_primary_only(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=2,
                primary_input=WDKStepTree(step_id=1),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByOrthologs", {"organism": "Pf3D7"}),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "transform"
        assert ast.root.primary_input is not None
        assert ast.root.primary_input.search_name == "GenesByTextSearch"
        assert ast.root.secondary_input is None

    def test_combine_without_operator_raises(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "S1"),
                "2": _wdk_step(2, "S2"),
                "3": _wdk_step(3, "BQ", {}),
            },
        )
        with pytest.raises(DataParsingError, match="boolean operator"):
            build_snapshot_from_wdk(wdk)

    def test_custom_name_preferred(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="GenesByTextSearch",
                    search_config=WDKSearchConfig(parameters={}),
                    custom_name="My Custom Step",
                    display_name="Text Search",
                ),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name == "My Custom Step"

    def test_display_name_fallback(self) -> None:
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="GenesByTextSearch",
                    search_config=WDKSearchConfig(parameters={}),
                    display_name="Text Search",
                ),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name == "Text Search"
