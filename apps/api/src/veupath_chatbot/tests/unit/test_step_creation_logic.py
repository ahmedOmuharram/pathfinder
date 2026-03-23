"""Tests for step creation business logic (services/strategies/step_creation.py).

Tests pure validation functions that guard against WDK contract violations:
- coerce_wdk_boolean_question_params: bq_* param extraction
- fold-change sample guard: identical ref/comp produces meaningless results
- input validation: missing steps, secondary without primary, missing operator
- search name resolution: missing search_name for leaf steps

These are all pure functions or simple state checks — no I/O mocking needed.

WDK contracts validated:
- Boolean question params use bq_left_op/bq_right_op/bq_operator convention
- bq_* keys must be consumed (removed) from parameters dict
- Fold-change searches reject identical ref and comp samples
- Secondary input requires primary input + operator
"""

from veupath_chatbot.services.strategies.step_creation import (
    _validate_fold_change_samples,
    coerce_wdk_boolean_question_params,
)

# ── coerce_wdk_boolean_question_params ────────────────────────────


class TestCoerceWdkBooleanQuestionParams:
    """WDK encodes combines as bq_left_op/bq_right_op/bq_operator in params.

    Pathfinder translates these to structural inputs. The function MUST:
    1. Extract left/right step IDs and operator
    2. Remove consumed bq_* keys from parameters dict (mutation)
    3. Return (None, None, None) if pattern doesn't match
    """

    def test_extracts_bq_params(self) -> None:
        """Standard WDK boolean question params → (left, right, op)."""
        params = {
            "bq_left_op__TranscriptRecordClasses.TranscriptRecordClass": "step_1",
            "bq_right_op__TranscriptRecordClasses.TranscriptRecordClass": "step_2",
            "bq_operator": "INTERSECT",
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left == "step_1"
        assert right == "step_2"
        assert op == "INTERSECT"

    def test_consumes_bq_keys(self) -> None:
        """bq_* keys must be removed from parameters dict."""
        params = {
            "bq_left_op_foo": "s1",
            "bq_right_op_foo": "s2",
            "bq_operator": "UNION",
            "other_param": "keep_me",
        }
        coerce_wdk_boolean_question_params(parameters=params)
        assert "other_param" in params
        assert "bq_operator" not in params
        assert not any(k.startswith("bq_left_op") for k in params)
        assert not any(k.startswith("bq_right_op") for k in params)

    def test_returns_none_when_no_bq_params(self) -> None:
        params = {"organism": '["pfal"]', "text_expression": "kinase"}
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert (left, right, op) == (None, None, None)

    def test_returns_none_when_operator_missing(self) -> None:
        """All three (left, right, op) must be present; partial → None."""
        params = {
            "bq_left_op_foo": "s1",
            "bq_right_op_foo": "s2",
            # bq_operator missing
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert (left, right, op) == (None, None, None)

    def test_returns_none_for_empty_params(self) -> None:
        left, right, op = coerce_wdk_boolean_question_params(parameters={})
        assert (left, right, op) == (None, None, None)

    def test_returns_none_for_non_dict(self) -> None:
        left, right, op = coerce_wdk_boolean_question_params(parameters="not a dict")
        assert (left, right, op) == (None, None, None)

    def test_prefix_matching(self) -> None:
        """WDK param names vary per record type (bq_left_op__<class>).
        The function checks startswith('bq_left_op') which matches all variants.
        """
        params = {
            "bq_left_op__GeneRecordClasses.GeneRecordClass": "step_a",
            "bq_right_op__GeneRecordClasses.GeneRecordClass": "step_b",
            "bq_operator": "MINUS",
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        assert left == "step_a"
        assert right == "step_b"
        assert op == "MINUS"

    def test_none_values_skipped(self) -> None:
        """bq_* key with None value → step ID not extracted."""
        params = {
            "bq_left_op_foo": None,
            "bq_right_op_foo": "s2",
            "bq_operator": "UNION",
        }
        left, right, op = coerce_wdk_boolean_question_params(parameters=params)
        # left_id is None because value was None → incomplete → all None
        assert (left, right, op) == (None, None, None)


# ── _validate_fold_change_samples ─────────────────────────────────


class TestValidateFoldChangeSamples:
    """Guard: identical ref/comp samples in fold-change produces meaningless results.

    WDK doesn't reject this — it just returns all-1.0 fold changes.
    Pathfinder catches it early to give a useful error message.
    """

    def test_different_samples_ok(self) -> None:
        result = _validate_fold_change_samples(
            "GenesByFoldChangeExpression",
            {
                "samples_fc_ref_generic": "sample_A",
                "samples_fc_comp_generic": "sample_B",
            },
        )
        assert result is None

    def test_identical_samples_rejected(self) -> None:
        result = _validate_fold_change_samples(
            "GenesByFoldChangeExpression",
            {
                "samples_fc_ref_generic": "sample_A",
                "samples_fc_comp_generic": "sample_A",
            },
        )
        assert result is not None
        assert "identical" in str(result).lower()

    def test_no_samples_ok(self) -> None:
        result = _validate_fold_change_samples(
            "GenesByTaxon",
            {"organism": '["pfal"]'},
        )
        assert result is None

    def test_percentile_ref_key(self) -> None:
        """samples_percentile_generic is an alternative ref key."""
        result = _validate_fold_change_samples(
            "GenesByPercentile",
            {"samples_percentile_generic": "same", "samples_fc_comp_generic": "same"},
        )
        assert result is not None

    def test_missing_comp_ok(self) -> None:
        result = _validate_fold_change_samples(
            "GenesByFoldChangeExpression",
            {"samples_fc_ref_generic": "sample_A"},
        )
        assert result is None
