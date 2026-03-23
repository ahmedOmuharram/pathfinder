"""Extended tests for WDK bridge: WDK <-> internal conversion edge cases.

Covers: operator translation, step type inference, missing/unexpected fields
in WDK responses, deep tree structures, and snapshot conversion boundaries.
"""

import pytest

from veupath_chatbot.domain.strategy.ops import CombineOp, parse_op
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearchConfig,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)
from veupath_chatbot.services.strategies.wdk_counts import plan_cache_key


def _wdk_step(
    step_id: int, search_name: str, params: dict[str, str] | None = None
) -> WDKStep:
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


# ===========================================================================
# Operator translation edge cases
# ===========================================================================


class TestOperatorTranslation:
    """Verify all WDK boolean operators round-trip correctly."""

    @pytest.mark.parametrize(
        ("wdk_value", "expected_op"),
        [
            ("INTERSECT", CombineOp.INTERSECT),
            ("UNION", CombineOp.UNION),
            ("MINUS", CombineOp.MINUS),
            ("RMINUS", CombineOp.RMINUS),
            ("LONLY", CombineOp.LONLY),
            ("RONLY", CombineOp.RONLY),
            ("COLOCATE", CombineOp.COLOCATE),
        ],
    )
    def test_standard_wdk_operators(
        self, wdk_value: str, expected_op: CombineOp
    ) -> None:
        """WDK BooleanOperator values parse to the matching CombineOp."""
        assert parse_op(wdk_value) == expected_op

    @pytest.mark.parametrize(
        ("alias", "expected_op"),
        [
            ("AND", CombineOp.INTERSECT),
            ("OR", CombineOp.UNION),
            ("NOT", CombineOp.MINUS),
            ("INTERSECTION", CombineOp.INTERSECT),
            ("PLUS", CombineOp.UNION),
            ("LEFT_MINUS", CombineOp.MINUS),
            ("RIGHT_MINUS", CombineOp.RMINUS),
        ],
    )
    def test_operator_aliases(self, alias: str, expected_op: CombineOp) -> None:
        """User-friendly aliases map to canonical operators."""
        assert parse_op(alias) == expected_op

    def test_case_insensitive(self) -> None:
        """Operator parsing is case-insensitive."""
        assert parse_op("intersect") == CombineOp.INTERSECT
        assert parse_op("Union") == CombineOp.UNION
        assert parse_op("mInUs") == CombineOp.MINUS

    def test_empty_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("   ")

    def test_unknown_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("XNOR")

    def test_hyphenated_operator_normalized(self) -> None:
        """Hyphens are normalized to underscores."""
        assert parse_op("LEFT-MINUS") == CombineOp.MINUS

    def test_spaced_operator_normalized(self) -> None:
        """Spaces are normalized to underscores."""
        assert parse_op("LEFT MINUS") == CombineOp.MINUS


# ===========================================================================
# Step type inference via build_snapshot_from_wdk
# ===========================================================================


class TestStepTypeInference:
    """Verify that leaf, transform, and combine steps are correctly inferred."""

    def test_search_step_has_no_inputs(self) -> None:
        """A step with no primaryInput or secondaryInput is a search (leaf)."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "GenesByTextSearch", {"text": "kinase"})},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "search"
        assert ast.root.primary_input is None
        assert ast.root.secondary_input is None

    def test_transform_step_has_primary_only(self) -> None:
        """A step with primaryInput but no secondaryInput is a transform."""
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=2,
                primary_input=WDKStepTree(step_id=1),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByRNASeqEvidence", {"threshold": "10"}),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "transform"
        assert ast.root.primary_input is not None
        assert ast.root.secondary_input is None

    def test_combine_step_has_both_inputs(self) -> None:
        """A step with both primaryInput and secondaryInput is a combine."""
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=3,
                primary_input=WDKStepTree(step_id=1),
                secondary_input=WDKStepTree(step_id=2),
            ),
            steps={
                "1": _wdk_step(1, "S1"),
                "2": _wdk_step(2, "S2"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "combine"
        assert ast.root.primary_input is not None
        assert ast.root.secondary_input is not None


# ===========================================================================
# Missing/unexpected fields in WDK responses
# ===========================================================================


class TestMissingFields:
    """Handle WDK responses with missing or unexpected fields."""

    def test_step_missing_from_steps_dict(self) -> None:
        """If a stepTree references a step that's not in the steps dict."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=999),
            steps={"1": _wdk_step(1, "S1")},
        )
        with pytest.raises(DataParsingError, match="Step 999 not found"):
            build_snapshot_from_wdk(wdk)

    def test_search_config_parameters_default_empty(self) -> None:
        """When searchConfig has no parameters, default to empty dict."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="S1",
                    search_config=WDKSearchConfig(),
                )
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.parameters == {}


# ===========================================================================
# Deep tree structures
# ===========================================================================


class TestDeepTreeStructures:
    """Verify conversion of multi-level step trees."""

    def test_three_level_tree(self) -> None:
        """A tree like: combine(combine(S1, S2), S3)."""
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=5,
                primary_input=WDKStepTree(
                    step_id=3,
                    primary_input=WDKStepTree(step_id=1),
                    secondary_input=WDKStepTree(step_id=2),
                ),
                secondary_input=WDKStepTree(step_id=4),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByGoTerm"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
                "4": _wdk_step(4, "GenesByLocation"),
                "5": _wdk_step(5, "BooleanQuestion", {"bq_operator": "UNION"}),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        # Root is UNION of (INTERSECT of S1,S2) and S4
        assert ast.root.infer_kind() == "combine"
        assert ast.root.operator == CombineOp.UNION
        left = ast.root.primary_input
        assert left is not None
        assert left.infer_kind() == "combine"
        assert left.operator == CombineOp.INTERSECT

    def test_transform_on_combine(self) -> None:
        """A transform step taking a combined result as input."""
        wdk = _strategy(
            step_tree=WDKStepTree(
                step_id=4,
                primary_input=WDKStepTree(
                    step_id=3,
                    primary_input=WDKStepTree(step_id=1),
                    secondary_input=WDKStepTree(step_id=2),
                ),
            ),
            steps={
                "1": _wdk_step(1, "GenesByTextSearch"),
                "2": _wdk_step(2, "GenesByGoTerm"),
                "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
                "4": _wdk_step(4, "GenesByOrthologs", {"organism": "Pf3D7"}),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.infer_kind() == "transform"
        assert ast.root.search_name == "GenesByOrthologs"
        input_node = ast.root.primary_input
        assert input_node is not None
        assert input_node.infer_kind() == "combine"


# ===========================================================================
# build_snapshot_from_wdk edge cases
# ===========================================================================


class TestSnapshotEdgeCases:
    """Edge cases in full snapshot conversion."""

    def test_strategy_with_empty_name(self) -> None:
        """Empty name should be treated as None."""
        wdk = _strategy(
            name="",
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "S1")},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.name is None

    def test_strategy_with_empty_description(self) -> None:
        """Empty description should be treated as None."""
        wdk = _strategy(
            description="",
            step_tree=WDKStepTree(step_id=1),
            steps={"1": _wdk_step(1, "S1")},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.description is None

    def test_step_ids_are_strings_in_ast(self) -> None:
        """AST step IDs should always be strings."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=42),
            steps={"42": _wdk_step(42, "S1")},
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.root.id == "42"
        assert isinstance(ast.root.id, str)

    def test_estimated_size_zero_preserved(self) -> None:
        """estimatedSize=0 should be preserved, not treated as falsy."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="S1",
                    search_config=WDKSearchConfig(parameters={}),
                    estimated_size=0,
                )
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.step_counts is not None
        assert ast.step_counts.get("1") == 0

    def test_estimated_size_negative_preserved(self) -> None:
        """Negative estimatedSize is technically valid (WDK uses -1 for unknown)."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=1),
            steps={
                "1": WDKStep(
                    id=1,
                    search_name="S1",
                    search_config=WDKSearchConfig(parameters={}),
                    estimated_size=-1,
                )
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.step_counts is not None
        assert ast.step_counts.get("1") == -1

    def test_wdk_step_ids_populated(self) -> None:
        """The AST should have wdk_step_ids populated for numeric step IDs."""
        wdk = _strategy(
            step_tree=WDKStepTree(step_id=100),
            steps={
                "100": WDKStep(
                    id=100,
                    search_name="GenesByTextSearch",
                    search_config=WDKSearchConfig(parameters={"text": "kinase"}),
                    estimated_size=500,
                ),
            },
        )
        ast = build_snapshot_from_wdk(wdk)
        assert ast.wdk_step_ids is not None
        assert ast.wdk_step_ids["100"] == 100
        assert ast.step_counts is not None
        assert ast.step_counts["100"] == 500


# ===========================================================================
# plan_cache_key edge cases
# ===========================================================================


class TestPlanCacheKeyEdgeCases:
    """Edge cases for plan cache key generation."""

    def test_key_order_does_not_matter(self) -> None:
        """json.dumps with sort_keys=True ensures key order doesn't matter."""
        plan1: JSONObject = {"a": 1, "b": 2}
        plan2: JSONObject = {"b": 2, "a": 1}
        assert plan_cache_key("site", plan1) == plan_cache_key("site", plan2)

    def test_empty_plan(self) -> None:
        """Empty plan should still produce a valid cache key."""
        key = plan_cache_key("site", {})
        assert "site:" in key
        assert len(key) > len("site:")

    def test_nested_plan(self) -> None:
        """Nested structures should be fully hashed."""
        plan: JSONObject = {
            "root": {
                "searchName": "S1",
                "primaryInput": {"searchName": "S2"},
            }
        }
        key = plan_cache_key("plasmo", plan)
        assert key.startswith("plasmo:")
