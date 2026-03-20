"""Tests for domain/parameters/canonicalize.py."""

import re
from typing import cast

import pytest

from veupath_chatbot.domain.parameters.canonicalize import (
    FAKE_ALL_SENTINEL,
    ParameterCanonicalizer,
)
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import ParamSpecConfig, make_param_spec


def _assert_validation_error(
    exc_info: pytest.ExceptionInfo[ValidationError], pattern: str
) -> None:
    """Assert that the ValidationError's detail matches the given pattern."""
    text = f"{exc_info.value.title} {exc_info.value.detail or ''}"
    assert re.search(pattern, text), (
        f"Pattern {pattern!r} not found in title={exc_info.value.title!r}, "
        f"detail={exc_info.value.detail!r}"
    )


def _canonicalizer(*specs: ParamSpecNormalized) -> ParameterCanonicalizer:
    return ParameterCanonicalizer(specs={s.name: s for s in specs})


# ---------------------------------------------------------------------------
# canonicalize() top-level dispatch
# ---------------------------------------------------------------------------
class TestCanonicalizeDispatch:
    def test_unknown_param_raises(self) -> None:
        c = _canonicalizer(make_param_spec(ParamSpecConfig(name="p1")))
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"unknown": "val"})
        _assert_validation_error(exc_info, "does not exist")

    def test_input_step_param_skipped(self) -> None:
        c = _canonicalizer(
            make_param_spec(
                ParamSpecConfig(name="inputStepId", param_type="input-step")
            )
        )
        result = c.canonicalize({"inputStepId": "123"})
        assert result == {}

    def test_empty_parameters(self) -> None:
        c = _canonicalizer(make_param_spec(ParamSpecConfig(name="p1")))
        result = c.canonicalize({})
        assert result == {}

    def test_none_parameters(self) -> None:
        c = _canonicalizer(make_param_spec(ParamSpecConfig(name="p1")))
        result = c.canonicalize(None)
        assert result == {}


# ---------------------------------------------------------------------------
# FAKE_ALL_SENTINEL rejection
# ---------------------------------------------------------------------------
class TestFakeAllSentinel:
    def test_rejected_at_top_level(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p1", param_type="string"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p1": FAKE_ALL_SENTINEL})
        _assert_validation_error(exc_info, re.escape(FAKE_ALL_SENTINEL))

    def test_rejected_in_multi_pick_list(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p1",
                param_type="multi-pick-vocabulary",
                vocabulary=[["a", "A"], ["b", "B"]],
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p1": [FAKE_ALL_SENTINEL]})
        _assert_validation_error(exc_info, re.escape(FAKE_ALL_SENTINEL))

    def test_rejected_for_single_pick(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p1",
                param_type="single-pick-vocabulary",
                vocabulary=[["a", "A"]],
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p1": FAKE_ALL_SENTINEL})
        _assert_validation_error(exc_info, re.escape(FAKE_ALL_SENTINEL))


# ---------------------------------------------------------------------------
# multi-pick-vocabulary
# ---------------------------------------------------------------------------
class TestMultiPickVocabulary:
    def test_list_values(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"], ["Toxoplasma", "Toxoplasma"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"organism": ["Plasmodium", "Toxoplasma"]})
        assert result["organism"] == ["Plasmodium", "Toxoplasma"]

    def test_csv_string(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"], ["Toxoplasma", "Toxoplasma"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"organism": "Plasmodium,Toxoplasma"})
        assert result["organism"] == ["Plasmodium", "Toxoplasma"]

    def test_json_array_string(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"organism": '["Plasmodium"]'})
        assert result["organism"] == ["Plasmodium"]

    def test_validates_count(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                min_selected=2,
                vocabulary=[["a", "a"]],
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"organism": ["a"]})
        _assert_validation_error(exc_info, "at least 2")

    def test_vocab_match(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["pf3d7", "Plasmodium falciparum 3D7"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"organism": ["Plasmodium falciparum 3D7"]})
        assert result["organism"] == ["pf3d7"]

    def test_none_value_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                allow_empty=True,
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"organism": None})
        assert result["organism"] == ""


# ---------------------------------------------------------------------------
# single-pick-vocabulary
# ---------------------------------------------------------------------------
class TestSinglePickVocabulary:
    def test_string_value(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                vocabulary=[["ring", "Ring"], ["troph", "Trophozoite"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"stage": "Ring"})
        assert result["stage"] == "ring"

    def test_multiple_values_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                vocabulary=[["a", "A"], ["b", "B"]],
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"stage": ["A", "B"]})
        _assert_validation_error(exc_info, "only one value")

    def test_empty_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                allow_empty=True,
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"stage": ""})
        assert result["stage"] == ""

    def test_empty_without_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                allow_empty=False,
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"stage": ""})
        _assert_validation_error(exc_info, "requires a value")

    def test_none_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                allow_empty=True,
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"stage": None})
        assert result["stage"] == ""


# ---------------------------------------------------------------------------
# scalar types: number, date, timestamp, string
# ---------------------------------------------------------------------------
class TestScalarTypes:
    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_string_value(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": "value"})
        assert result["p"] == "value"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_integer_value(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": 42})
        assert result["p"] == "42"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_bool_value(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": True})
        assert result["p"] == "true"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_list_value_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": [1, 2]})
        _assert_validation_error(exc_info, "scalar")

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_dict_value_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": {"min": 1}})
        _assert_validation_error(exc_info, "scalar")

    def test_none_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="p", param_type="string", allow_empty=True)
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": None})
        assert result["p"] == ""


# ---------------------------------------------------------------------------
# number-range / date-range
# ---------------------------------------------------------------------------
class TestRangeTypes:
    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_dict_passthrough(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": {"min": 1, "max": 10}})
        assert result["p"] == {"min": 1, "max": 10}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_list_pair(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": [1, 10]})
        assert result["p"] == {"min": 1, "max": 10}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_tuple_pair(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        result = c.canonicalize(cast("dict[str, object]", {"p": (5, 15)}))
        assert result["p"] == {"min": 5, "max": 15}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_invalid_value_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": "invalid"})
        _assert_validation_error(exc_info, "must be a range")

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_wrong_length_list_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": [1, 2, 3]})
        _assert_validation_error(exc_info, "must be a range")


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------
class TestFilterType:
    def test_dict_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": {"filters": []}})
        assert result["p"] == {"filters": []}

    def test_list_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": [{"field": "x"}]})
        assert result["p"] == [{"field": "x"}]

    def test_string_stringified(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": "some_filter"})
        assert result["p"] == "some_filter"

    def test_number_stringified(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": 42})
        assert result["p"] == "42"


# ---------------------------------------------------------------------------
# input-dataset
# ---------------------------------------------------------------------------
class TestInputDataset:
    def test_single_list_item(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["dataset_1"]})
        assert result["p"] == "dataset_1"

    def test_multi_list_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": ["a", "b"]})
        _assert_validation_error(exc_info, "single value")

    def test_string_value(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": "dataset_1"})
        assert result["p"] == "dataset_1"

    def test_integer_value(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": 42})
        assert result["p"] == "42"


# ---------------------------------------------------------------------------
# unknown param type
# ---------------------------------------------------------------------------
class TestUnknownParamType:
    def test_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="unknown_type"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": {"complex": "data"}})
        assert result["p"] == {"complex": "data"}


# ---------------------------------------------------------------------------
# _enforce_leaf_values / _enforce_leaf_value
# ---------------------------------------------------------------------------
class TestEnforceLeafValues:
    """Test leaf enforcement for count_only_leaves vocabularies."""

    @staticmethod
    def _tree_vocab() -> dict:
        return {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {
                    "data": {"term": "parent", "display": "Parent"},
                    "children": [
                        {
                            "data": {"term": "leaf1", "display": "Leaf 1"},
                            "children": [],
                        },
                        {
                            "data": {"term": "leaf2", "display": "Leaf 2"},
                            "children": [],
                        },
                    ],
                },
                {
                    "data": {"term": "solo", "display": "Solo"},
                    "children": [],
                },
            ],
        }

    def test_leaf_value_passes_through(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["leaf1"]})
        assert result["p"] == ["leaf1"]

    def test_parent_expands_to_leaves(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["Parent"]})
        assert result["p"] == ["leaf1", "leaf2"]

    def test_root_expands_to_all_leaves(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["Root"]})
        assert result["p"] == ["leaf1", "leaf2", "solo"]

    def test_deduplicates_leaves(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["Parent", "leaf1"]})
        # leaf1 is in Parent's leaves, so should be deduplicated
        assert result["p"] == ["leaf1", "leaf2"]

    def test_no_match_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": ["nonexistent"]})
        _assert_validation_error(exc_info, "does not accept")

    def test_count_only_leaves_false_no_expansion(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=False,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["Parent"]})
        # Without count_only_leaves, "Parent" should be kept as-is (after vocab match)
        assert result["p"] == ["parent"]

    def test_single_pick_leaf_enforcement(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": "leaf1"})
        assert result["p"] == "leaf1"

    def test_single_pick_non_leaf_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._tree_vocab(),
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": "Parent"})
        _assert_validation_error(exc_info, "requires leaf")


# ---------------------------------------------------------------------------
# _expand_leaf_terms_for_match / _find_leaf_term_for_match
# ---------------------------------------------------------------------------
class TestExpandLeafTerms:
    """Direct tests for the tree-walking helpers."""

    @staticmethod
    def _tree() -> dict:
        return {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {
                    "data": {"term": "A", "display": "Node A"},
                    "children": [
                        {"data": {"term": "A1", "display": "Leaf A1"}, "children": []},
                        {"data": {"term": "A2", "display": "Leaf A2"}, "children": []},
                    ],
                },
                {
                    "data": {"term": "B", "display": "Node B"},
                    "children": [],
                },
            ],
        }

    def test_expand_leaf_on_leaf_returns_self(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "B")
        assert result == ["B"]

    def test_expand_leaf_on_parent_returns_children(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "A")
        assert result == ["A1", "A2"]

    def test_expand_leaf_on_root(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "root")
        assert result == ["A1", "A2", "B"]

    def test_expand_leaf_match_by_display(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "Node A")
        assert result == ["A1", "A2"]

    def test_expand_leaf_no_match(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "nonexistent")
        assert result == []

    def test_expand_leaf_non_dict_vocab(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match([["a", "A"]], "a")
        assert result == []

    def test_expand_leaf_empty_match(self) -> None:
        c = _canonicalizer()
        result = c._expand_leaf_terms_for_match(self._tree(), "")
        assert result == []

    def test_find_leaf_on_leaf_returns_term(self) -> None:
        c = _canonicalizer()
        result = c._find_leaf_term_for_match(self._tree(), "B")
        assert result == "B"

    def test_find_leaf_on_parent_returns_none(self) -> None:
        c = _canonicalizer()
        result = c._find_leaf_term_for_match(self._tree(), "A")
        assert result is None

    def test_find_leaf_no_match_returns_none(self) -> None:
        c = _canonicalizer()
        result = c._find_leaf_term_for_match(self._tree(), "nonexistent")
        assert result is None

    def test_find_leaf_non_dict_vocab_returns_none(self) -> None:
        c = _canonicalizer()
        result = c._find_leaf_term_for_match([["a", "A"]], "a")
        assert result is None

    def test_find_leaf_empty_match_returns_none(self) -> None:
        c = _canonicalizer()
        result = c._find_leaf_term_for_match(self._tree(), "")
        assert result is None
