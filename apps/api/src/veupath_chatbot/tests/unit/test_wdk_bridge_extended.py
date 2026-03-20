"""Extended tests for WDK bridge: WDK <-> internal conversion edge cases.

Covers: operator translation, step type inference, missing/unexpected fields
in WDK responses, deep tree structures, and snapshot conversion boundaries.
"""

import pytest

from veupath_chatbot.domain.strategy.ops import CombineOp, parse_op
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_node_from_wdk,
    build_snapshot_from_wdk,
    extract_estimated_size,
    extract_operator,
    extract_record_type,
    get_step_info,
)
from veupath_chatbot.services.strategies.wdk_counts import plan_cache_key


def _wdk_step(step_id: int, search_name: str, params: dict | None = None) -> dict:
    return {
        "searchName": search_name,
        "searchConfig": {"parameters": params or {}},
    }


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
# extract_operator edge cases
# ===========================================================================


class TestExtractOperatorEdgeCases:
    """Edge cases in operator extraction from WDK step parameters."""

    def test_list_value_extracts_first(self) -> None:
        """WDK may return multi-valued params as lists."""
        params: JSONObject = {"bq_operator": ["INTERSECT", "UNION"]}
        assert extract_operator(params) == "INTERSECT"

    def test_empty_list_returns_none(self) -> None:
        params: JSONObject = {"bq_operator": []}
        assert extract_operator(params) is None

    def test_key_with_operator_substring(self) -> None:
        """Any key containing 'operator' (case-insensitive) is matched."""
        params: JSONObject = {"my_OPERATOR_field": "UNION"}
        assert extract_operator(params) == "UNION"

    def test_non_string_non_list_value(self) -> None:
        """If the operator value is neither string nor list, it's skipped."""
        params: JSONObject = {"bq_operator": 42}
        assert extract_operator(params) is None

    def test_multiple_operator_keys_returns_first_match(self) -> None:
        """First matching key in iteration order wins."""
        params: JSONObject = {"bq_operator": "INTERSECT", "other_operator": "UNION"}
        result = extract_operator(params)
        assert result in ("INTERSECT", "UNION")


# ===========================================================================
# Step type inference in build_node_from_wdk
# ===========================================================================


class TestStepTypeInference:
    """Verify that leaf, transform, and combine steps are correctly inferred."""

    def test_search_step_has_no_inputs(self) -> None:
        """A step with no primaryInput or secondaryInput is a search (leaf)."""
        step_tree: JSONObject = {"stepId": 1}
        steps: JSONObject = {"1": _wdk_step(1, "GenesByTextSearch", {"text": "kinase"})}
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.infer_kind() == "search"
        assert node.primary_input is None
        assert node.secondary_input is None

    def test_transform_step_has_primary_only(self) -> None:
        """A step with primaryInput but no secondaryInput is a transform."""
        step_tree: JSONObject = {
            "stepId": 2,
            "primaryInput": {"stepId": 1},
        }
        steps: JSONObject = {
            "1": _wdk_step(1, "GenesByTextSearch"),
            "2": _wdk_step(2, "GenesByRNASeqEvidence", {"threshold": "10"}),
        }
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.infer_kind() == "transform"
        assert node.primary_input is not None
        assert node.secondary_input is None

    def test_combine_step_has_both_inputs(self) -> None:
        """A step with both primaryInput and secondaryInput is a combine."""
        step_tree: JSONObject = {
            "stepId": 3,
            "primaryInput": {"stepId": 1},
            "secondaryInput": {"stepId": 2},
        }
        steps: JSONObject = {
            "1": _wdk_step(1, "S1"),
            "2": _wdk_step(2, "S2"),
            "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "UNION"}),
        }
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.infer_kind() == "combine"
        assert node.primary_input is not None
        assert node.secondary_input is not None


# ===========================================================================
# Missing/unexpected fields in WDK responses
# ===========================================================================


class TestMissingFields:
    """Handle WDK responses with missing or unexpected fields."""

    def test_step_missing_from_steps_dict(self) -> None:
        """If a stepTree references a step that's not in the steps dict."""
        step_tree: JSONObject = {"stepId": 999}
        steps: JSONObject = {"1": _wdk_step(1, "S1")}
        with pytest.raises(DataParsingError, match="Step 999 not found"):
            build_node_from_wdk(step_tree, steps, "gene")

    def test_step_id_not_integer(self) -> None:
        """stepId must be an integer."""
        step_tree: JSONObject = {"stepId": "abc"}
        with pytest.raises(DataParsingError, match="stepId"):
            build_node_from_wdk(step_tree, {}, "gene")

    def test_step_id_none_raises(self) -> None:
        step_tree: JSONObject = {"stepId": None}
        with pytest.raises(DataParsingError, match="stepId"):
            build_node_from_wdk(step_tree, {}, "gene")

    def test_search_config_parameters_missing(self) -> None:
        """When searchConfig has no parameters key, default to empty dict."""
        step_tree: JSONObject = {"stepId": 1}
        steps: JSONObject = {"1": {"searchName": "S1", "searchConfig": {}}}
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.parameters == {}

    def test_extra_fields_in_step_info_ignored(self) -> None:
        """Extra fields in the step info dict should be safely ignored."""
        step_tree: JSONObject = {"stepId": 1}
        steps: JSONObject = {
            "1": {
                "searchName": "GenesByTextSearch",
                "searchConfig": {"parameters": {"text": "kinase"}},
                "estimatedSize": 42,
                "isValid": True,
                "validationBundle": {"level": "SYNTACTIC"},
                "unknownField": "should be ignored",
            }
        }
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.search_name == "GenesByTextSearch"
        assert node.parameters == {"text": "kinase"}

    def test_extra_fields_in_step_tree_ignored(self) -> None:
        """Extra fields in the stepTree (like answerSpec) are safely ignored."""
        step_tree: JSONObject = {
            "stepId": 1,
            "answerSpec": {"questionName": "GenesByTextSearch"},
            "isCollapsible": False,
        }
        steps: JSONObject = {"1": _wdk_step(1, "GenesByTextSearch")}
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.search_name == "GenesByTextSearch"


# ===========================================================================
# Deep tree structures
# ===========================================================================


class TestDeepTreeStructures:
    """Verify conversion of multi-level step trees."""

    def test_three_level_tree(self) -> None:
        """A tree like: combine(combine(S1, S2), S3)."""
        step_tree: JSONObject = {
            "stepId": 5,
            "primaryInput": {
                "stepId": 3,
                "primaryInput": {"stepId": 1},
                "secondaryInput": {"stepId": 2},
            },
            "secondaryInput": {"stepId": 4},
        }
        steps: JSONObject = {
            "1": _wdk_step(1, "GenesByTextSearch"),
            "2": _wdk_step(2, "GenesByGoTerm"),
            "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
            "4": _wdk_step(4, "GenesByLocation"),
            "5": _wdk_step(5, "BooleanQuestion", {"bq_operator": "UNION"}),
        }
        node = build_node_from_wdk(step_tree, steps, "gene")
        # Root is UNION of (INTERSECT of S1,S2) and S4
        assert node.infer_kind() == "combine"
        assert node.operator == CombineOp.UNION
        left = node.primary_input
        assert left is not None
        assert left.infer_kind() == "combine"
        assert left.operator == CombineOp.INTERSECT

    def test_transform_on_combine(self) -> None:
        """A transform step taking a combined result as input."""
        step_tree: JSONObject = {
            "stepId": 4,
            "primaryInput": {
                "stepId": 3,
                "primaryInput": {"stepId": 1},
                "secondaryInput": {"stepId": 2},
            },
        }
        steps: JSONObject = {
            "1": _wdk_step(1, "GenesByTextSearch"),
            "2": _wdk_step(2, "GenesByGoTerm"),
            "3": _wdk_step(3, "BooleanQuestion", {"bq_operator": "INTERSECT"}),
            "4": _wdk_step(4, "GenesByOrthologs", {"organism": "Pf3D7"}),
        }
        node = build_node_from_wdk(step_tree, steps, "gene")
        assert node.infer_kind() == "transform"
        assert node.search_name == "GenesByOrthologs"
        input_node = node.primary_input
        assert input_node is not None
        assert input_node.infer_kind() == "combine"


# ===========================================================================
# build_snapshot_from_wdk edge cases
# ===========================================================================


class TestSnapshotEdgeCases:
    """Edge cases in full snapshot conversion."""

    def test_strategy_with_null_name(self) -> None:
        """WDK may return null for strategy name."""
        wdk = {
            "recordClassName": "gene",
            "name": None,
            "stepTree": {"stepId": 1},
            "steps": {"1": _wdk_step(1, "S1")},
        }
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.name is None

    def test_strategy_with_null_description(self) -> None:
        wdk = {
            "recordClassName": "gene",
            "description": None,
            "stepTree": {"stepId": 1},
            "steps": {"1": _wdk_step(1, "S1")},
        }
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.description is None

    def test_strategy_with_integer_name(self) -> None:
        """Non-string name should not crash (WDK shouldn't do this, but be safe)."""
        wdk = {
            "recordClassName": "gene",
            "name": 12345,
            "stepTree": {"stepId": 1},
            "steps": {"1": _wdk_step(1, "S1")},
        }
        ast, _, _ = build_snapshot_from_wdk(wdk)
        # Non-string names should be treated as None
        assert ast.name is None

    def test_step_ids_are_strings_in_ast(self) -> None:
        """AST step IDs should always be strings."""
        wdk = {
            "recordClassName": "gene",
            "stepTree": {"stepId": 42},
            "steps": {"42": _wdk_step(42, "S1")},
        }
        ast, _, _ = build_snapshot_from_wdk(wdk)
        assert ast.root.id == "42"
        assert isinstance(ast.root.id, str)

    def test_estimated_size_zero_preserved(self) -> None:
        """estimatedSize=0 should be preserved, not treated as falsy."""
        step_info: JSONObject = {"estimatedSize": 0}
        assert extract_estimated_size(step_info) == 0

    def test_estimated_size_negative(self) -> None:
        """Negative estimatedSize is technically valid (WDK uses -1 for unknown)."""
        step_info: JSONObject = {"estimatedSize": -1}
        assert extract_estimated_size(step_info) == -1

    def test_estimated_size_float_returns_none(self) -> None:
        """Float estimatedSize is not valid (must be int)."""
        step_info: JSONObject = {"estimatedSize": 42.5}
        assert extract_estimated_size(step_info) is None

    def test_steps_data_includes_wdk_step_id(self) -> None:
        """The steps_data list should have wdkStepId populated."""
        wdk = {
            "recordClassName": "gene",
            "stepTree": {"stepId": 100},
            "steps": {
                "100": {
                    "searchName": "GenesByTextSearch",
                    "searchConfig": {"parameters": {"text": "kinase"}},
                    "estimatedSize": 500,
                }
            },
        }
        _, steps_data, _ = build_snapshot_from_wdk(wdk)
        assert len(steps_data) >= 1
        step = steps_data[0]
        assert isinstance(step, dict)
        assert step.get("wdkStepId") == 100
        assert step.get("resultCount") == 500


# ===========================================================================
# extract_record_type edge cases
# ===========================================================================


class TestRecordTypeExtraction:
    """Edge cases for record type extraction from WDK strategy."""

    def test_whitespace_padded_value(self) -> None:
        """Should strip whitespace."""
        assert (
            extract_record_type({"recordClassName": "  transcript  "}) == "transcript"
        )

    def test_numeric_value_raises(self) -> None:
        with pytest.raises(DataParsingError, match="recordClassName"):
            extract_record_type({"recordClassName": 42})

    def test_boolean_value_raises(self) -> None:
        with pytest.raises(DataParsingError, match="recordClassName"):
            extract_record_type({"recordClassName": True})

    def test_list_value_raises(self) -> None:
        with pytest.raises(DataParsingError, match="recordClassName"):
            extract_record_type({"recordClassName": ["gene"]})


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


# ===========================================================================
# get_step_info edge cases
# ===========================================================================


class TestGetStepInfoEdgeCases:
    """Edge cases for step info lookup."""

    def test_step_id_string_conversion(self) -> None:
        """Steps dict keys are strings, but step_id is int -- must convert."""
        steps: JSONObject = {"42": {"searchName": "S1"}}
        result = get_step_info(steps, 42)
        assert result["searchName"] == "S1"

    def test_step_value_not_dict_raises(self) -> None:
        """If the step entry is not a dict, it should raise."""
        steps: JSONObject = {"42": "not_a_dict"}
        with pytest.raises(DataParsingError, match="Step 42 not found"):
            get_step_info(steps, 42)

    def test_step_value_none_raises(self) -> None:
        steps: JSONObject = {"42": None}
        with pytest.raises(DataParsingError, match="Step 42 not found"):
            get_step_info(steps, 42)

    def test_large_step_id(self) -> None:
        """WDK step IDs can be large longs."""
        big_id = 999999999
        steps: JSONObject = {str(big_id): {"searchName": "S1"}}
        result = get_step_info(steps, big_id)
        assert result["searchName"] == "S1"
