"""Tests for WDK -> AST conversion (services/strategies/wdk_conversion.py).

Verifies that typed WDK strategy models are correctly converted to internal
AST representation. These functions are critical for strategy import:
wrong parsing silently corrupts imported strategies.

Public API under test:
- build_snapshot_from_wdk(WDKStrategyDetails) -> (StrategyAST, JSONArray, JSONObject)
"""

import pytest

from veupath_chatbot.domain.strategy.ops import CombineOp
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

# ── Helpers ─────────────────────────────────────────────────────────


def _make_step(
    step_id: int,
    search_name: str,
    parameters: dict[str, str] | None = None,
    estimated_size: int | None = None,
    custom_name: str | None = None,
    display_name: str = "",
) -> WDKStep:
    """Shorthand to construct a WDKStep with sensible defaults."""
    return WDKStep(
        id=step_id,
        search_name=search_name,
        search_config=WDKSearchConfig(parameters=parameters or {}),
        estimated_size=estimated_size,
        custom_name=custom_name,
        display_name=display_name,
    )


def _make_strategy(
    *,
    name: str = "Test",
    root_step_id: int = 100,
    record_class_name: str | None = "transcript",
    step_tree: WDKStepTree | None = None,
    steps: dict[str, WDKStep] | None = None,
    description: str = "",
) -> WDKStrategyDetails:
    """Shorthand to construct a WDKStrategyDetails with sensible defaults."""
    if step_tree is None:
        step_tree = WDKStepTree(step_id=root_step_id)
    if steps is None:
        steps = {
            str(root_step_id): _make_step(root_step_id, "GenesByTaxon"),
        }
    return WDKStrategyDetails(
        strategy_id=200,
        name=name,
        root_step_id=root_step_id,
        record_class_name=record_class_name,
        step_tree=step_tree,
        steps=steps,
        description=description,
    )


# ── build_snapshot_from_wdk: AST shape ────────────────────────────


class TestBuildSnapshotAst:
    """Verify that the returned StrategyAST has the right shape and values."""

    def test_single_step_strategy(self) -> None:
        """Single-step strategy produces correct AST fields."""
        wdk = _make_strategy(
            name="My Strategy",
            description="Test strategy",
            steps={
                "100": _make_step(
                    100,
                    "GenesByTaxon",
                    parameters={"organism": "Plasmodium falciparum"},
                    estimated_size=5000,
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.record_type == "transcript"
        assert ast.name == "My Strategy"
        assert ast.description == "Test strategy"
        assert ast.root.search_name == "GenesByTaxon"

    def test_name_and_description_none_when_empty(self) -> None:
        """Empty name and description map to None in the AST."""
        wdk = _make_strategy(name="", description="")
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.name is None
        assert ast.description is None

    def test_record_type_stripped(self) -> None:
        """Leading/trailing whitespace is stripped from recordClassName."""
        wdk = _make_strategy(record_class_name="  transcript  ")
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.record_type == "transcript"


# ── build_snapshot_from_wdk: step counts ──────────────────────────


class TestBuildSnapshotStepCounts:
    """Verify that step_counts (third return value) is populated correctly."""

    def test_single_step_count(self) -> None:
        """Step with estimatedSize appears in step_counts."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon", estimated_size=5000),
            },
        )
        _, _, step_counts = build_snapshot_from_wdk(wdk)
        assert step_counts["100"] == 5000

    def test_multi_step_counts(self) -> None:
        """Multi-step combine strategy tracks counts for all steps."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(
                    100, "GenesByTaxon",
                    parameters={"organism": "pfal"},
                    estimated_size=5000,
                ),
                "200": _make_step(
                    200, "GenesByText",
                    parameters={"text_expression": "kinase"},
                    estimated_size=200,
                ),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "INTERSECT", "bq_input_step": ""},
                    estimated_size=150,
                ),
            },
        )
        _, _, step_counts = build_snapshot_from_wdk(wdk)
        assert step_counts["100"] == 5000
        assert step_counts["200"] == 200
        assert step_counts["300"] == 150

    def test_missing_estimated_size_excluded(self) -> None:
        """Steps without estimatedSize should not appear in step_counts."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon"),
            },
        )
        _, _, step_counts = build_snapshot_from_wdk(wdk)
        assert "100" not in step_counts

    def test_zero_estimated_size_included(self) -> None:
        """Steps with estimatedSize=0 should still appear in step_counts."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon", estimated_size=0),
            },
        )
        _, _, step_counts = build_snapshot_from_wdk(wdk)
        assert step_counts["100"] == 0


# ── build_snapshot_from_wdk: steps_data enrichment ────────────────


class TestBuildSnapshotStepsData:
    """Verify the steps_data (second return value) is enriched correctly."""

    def test_steps_data_count(self) -> None:
        """steps_data should have one entry per step in the tree."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(100, "GenesByTaxon", parameters={"organism": "pfal"}),
                "200": _make_step(200, "GenesByText", parameters={"text_expression": "kinase"}),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "INTERSECT", "bq_input_step": ""},
                ),
            },
        )
        _, steps_data, _ = build_snapshot_from_wdk(wdk)
        assert len(steps_data) == 3

    def test_steps_data_has_wdk_step_id(self) -> None:
        """Each step in steps_data should have wdkStepId set."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon", estimated_size=500),
            },
        )
        _, steps_data, _ = build_snapshot_from_wdk(wdk)
        assert any(
            s.get("wdkStepId") == 100
            for s in steps_data
            if isinstance(s, dict)
        )

    def test_steps_data_has_result_count(self) -> None:
        """Steps with estimatedSize should get resultCount in steps_data."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon", estimated_size=500),
            },
        )
        _, steps_data, _ = build_snapshot_from_wdk(wdk)
        assert any(
            s.get("resultCount") == 500
            for s in steps_data
            if isinstance(s, dict)
        )

    def test_steps_data_result_count_none_when_no_size(self) -> None:
        """Steps without estimatedSize should have resultCount=None in steps_data."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon"),
            },
        )
        _, steps_data, _ = build_snapshot_from_wdk(wdk)
        step = next(
            s for s in steps_data
            if isinstance(s, dict) and s.get("wdkStepId") == 100
        )
        assert step.get("resultCount") is None


# ── Node construction via build_snapshot_from_wdk ───────────────────


class TestNodeConstruction:
    """Tests that verify node building behavior through the public API."""

    def test_leaf_step(self) -> None:
        """Simple search step (no inputs) produces a search node."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(
                    100,
                    "GenesByTaxon",
                    parameters={"organism": "Plasmodium falciparum"},
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.search_name == "GenesByTaxon"
        assert ast.root.id == "100"
        assert ast.root.parameters == {"organism": "Plasmodium falciparum"}
        assert ast.root.primary_input is None
        assert ast.root.secondary_input is None
        assert ast.root.infer_kind() == "search"

    def test_transform_step(self) -> None:
        """Step with primary input only produces a transform node."""
        wdk = _make_strategy(
            root_step_id=200,
            step_tree=WDKStepTree(
                step_id=200,
                primary_input=WDKStepTree(step_id=100),
            ),
            steps={
                "100": _make_step(
                    100, "GenesByTaxon", parameters={"organism": "pfal"},
                ),
                "200": _make_step(
                    200, "GenesByOrthologPattern",
                    parameters={"pattern": "%PFAL:Y%"},
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.search_name == "GenesByOrthologPattern"
        assert ast.root.primary_input is not None
        assert ast.root.primary_input.search_name == "GenesByTaxon"
        assert ast.root.secondary_input is None
        assert ast.root.infer_kind() == "transform"

    def test_combine_step(self) -> None:
        """Step with both inputs produces a combine node with operator."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(
                    100, "GenesByTaxon", parameters={"organism": "pfal"},
                ),
                "200": _make_step(
                    200, "GenesByText",
                    parameters={"text_expression": "kinase"},
                ),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "INTERSECT", "bq_input_step": ""},
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "combine"
        assert ast.root.operator == CombineOp.INTERSECT
        assert ast.root.primary_input is not None
        assert ast.root.secondary_input is not None
        assert ast.root.primary_input.search_name == "GenesByTaxon"
        assert ast.root.secondary_input.search_name == "GenesByText"

    def test_combine_union_operator(self) -> None:
        """UNION operator is correctly parsed in combine steps."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(100, "S1"),
                "200": _make_step(200, "S2"),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "UNION", "bq_input_step": ""},
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.operator == CombineOp.UNION

    def test_combine_minus_operator(self) -> None:
        """MINUS operator is correctly parsed in combine steps."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(100, "S1"),
                "200": _make_step(200, "S2"),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "MINUS", "bq_input_step": ""},
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.operator == CombineOp.MINUS

    def test_deep_nested_tree(self) -> None:
        """Three-level tree is correctly built with all nodes linked."""
        wdk = _make_strategy(
            root_step_id=500,
            step_tree=WDKStepTree(
                step_id=500,
                primary_input=WDKStepTree(
                    step_id=300,
                    primary_input=WDKStepTree(step_id=100),
                    secondary_input=WDKStepTree(step_id=200),
                ),
                secondary_input=WDKStepTree(step_id=400),
            ),
            steps={
                "100": _make_step(100, "GenesByTaxon", parameters={"organism": "pfal"}),
                "200": _make_step(200, "GenesByText", parameters={"text_expression": "kinase"}),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "INTERSECT", "bq_input_step": ""},
                ),
                "400": _make_step(400, "GenesByGoTerm", parameters={"go_term": "GO:0006915"}),
                "500": _make_step(
                    500, "boolean_question_2",
                    parameters={"bq_operator": "UNION", "bq_input_step": ""},
                ),
            },
        )
        ast, steps_data, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "combine"
        assert ast.root.operator == CombineOp.UNION

        inner_combine = ast.root.primary_input
        assert inner_combine is not None
        assert inner_combine.infer_kind() == "combine"
        assert inner_combine.operator == CombineOp.INTERSECT
        assert inner_combine.primary_input is not None
        assert inner_combine.primary_input.search_name == "GenesByTaxon"
        assert inner_combine.secondary_input is not None
        assert inner_combine.secondary_input.search_name == "GenesByText"

        assert ast.root.secondary_input is not None
        assert ast.root.secondary_input.search_name == "GenesByGoTerm"
        assert len(steps_data) == 5

    def test_empty_parameters_produces_empty_dict(self) -> None:
        """Step with empty searchConfig.parameters yields empty params dict."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon", parameters={}),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.parameters == {}

    def test_multiple_parameters_preserved(self) -> None:
        """All parameters from searchConfig are preserved in the AST node."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(
                    100, "GenesByTaxon",
                    parameters={
                        "organism": '["Plasmodium falciparum 3D7"]',
                        "nonterminal_param": "value",
                    },
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.parameters["organism"] == '["Plasmodium falciparum 3D7"]'
        assert ast.root.parameters["nonterminal_param"] == "value"


# ── Display name resolution ────────────────────────────────────────


class TestDisplayName:
    """Verify display name resolution: customName > displayName > None."""

    def test_custom_name_used(self) -> None:
        """customName on WDKStep maps to displayName on AST node."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(
                    100, "GenesByTaxon", custom_name="My Custom Step",
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name == "My Custom Step"

    def test_display_name_field_used(self) -> None:
        """displayName on WDKStep used when customName is absent."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(
                    100, "GenesByTaxon", display_name="Genes by Taxon",
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name == "Genes by Taxon"

    def test_custom_name_takes_priority(self) -> None:
        """customName takes priority over displayName."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(
                    100, "GenesByTaxon",
                    custom_name="Custom",
                    display_name="Display",
                ),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name == "Custom"

    def test_no_name_yields_none(self) -> None:
        """No customName and empty displayName yields None."""
        wdk = _make_strategy(
            steps={
                "100": _make_step(100, "GenesByTaxon"),
            },
        )
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.display_name is None


# ── Error paths ─────────────────────────────────────────────────────


class TestBuildSnapshotErrors:
    """Verify that invalid inputs raise DataParsingError with clear messages."""

    def test_missing_record_class_name_raises(self) -> None:
        """Strategy with None recordClassName raises DataParsingError."""
        wdk = _make_strategy(record_class_name=None)
        with pytest.raises(DataParsingError, match="recordClassName"):
            build_snapshot_from_wdk(wdk)

    def test_empty_record_class_name_raises(self) -> None:
        """Strategy with empty recordClassName raises DataParsingError."""
        wdk = _make_strategy(record_class_name="")
        with pytest.raises(DataParsingError, match="recordClassName"):
            build_snapshot_from_wdk(wdk)

    def test_whitespace_record_class_name_raises(self) -> None:
        """Strategy with whitespace-only recordClassName raises DataParsingError."""
        wdk = _make_strategy(record_class_name="   ")
        with pytest.raises(DataParsingError, match="recordClassName"):
            build_snapshot_from_wdk(wdk)

    def test_missing_step_in_steps_dict_raises(self) -> None:
        """Step referenced in stepTree but absent from steps dict raises."""
        wdk = _make_strategy(
            step_tree=WDKStepTree(step_id=999),
            steps={
                "100": _make_step(100, "GenesByTaxon"),
            },
        )
        with pytest.raises(DataParsingError, match="Step 999 not found"):
            build_snapshot_from_wdk(wdk)

    def test_combine_without_operator_raises(self) -> None:
        """Combine step must have an operator in parameters."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(100, "S1"),
                "200": _make_step(200, "S2"),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_input_step": ""},
                ),
            },
        )
        with pytest.raises(DataParsingError, match="boolean operator"):
            build_snapshot_from_wdk(wdk)

    def test_missing_secondary_step_in_nested_tree_raises(self) -> None:
        """Missing step in a nested secondary input raises DataParsingError."""
        wdk = _make_strategy(
            root_step_id=300,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": _make_step(100, "GenesByTaxon"),
                "300": _make_step(
                    300, "boolean_question_1",
                    parameters={"bq_operator": "INTERSECT", "bq_input_step": ""},
                ),
            },
        )
        with pytest.raises(DataParsingError, match="Step 200 not found"):
            build_snapshot_from_wdk(wdk)
