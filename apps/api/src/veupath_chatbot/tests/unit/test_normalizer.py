"""Tests for domain/parameters/normalize.py (ParameterNormalizer).

These test the normalizer directly, without going through the StrategyCompiler.
The existing test_param_normalization.py tests the normalizer indirectly through
compilation with WDK fixtures.
"""

import json

import pytest

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import ParamSpecConfig, make_param_spec


def _normalizer(*specs: ParamSpecNormalized) -> ParameterNormalizer:
    return ParameterNormalizer(specs={s.name: s for s in specs})


# ---------------------------------------------------------------------------
# normalize() top-level
# ---------------------------------------------------------------------------
class TestNormalizeDispatch:
    def test_unknown_param_raises(self) -> None:
        n = _normalizer(make_param_spec(ParamSpecConfig(name="p1")))
        with pytest.raises(ValidationError, match="Unknown parameter"):
            n.normalize({"unknown": "val"})

    def test_input_step_param_skipped(self) -> None:
        n = _normalizer(
            make_param_spec(
                ParamSpecConfig(name="inputStepId", param_type="input-step")
            )
        )
        result = n.normalize({"inputStepId": "123"})
        assert result == {}

    def test_empty_parameters(self) -> None:
        n = _normalizer(make_param_spec(ParamSpecConfig(name="p1")))
        result = n.normalize({})
        assert result == {}

    def test_none_parameters(self) -> None:
        n = _normalizer(make_param_spec(ParamSpecConfig(name="p1")))
        result = n.normalize(None)
        assert result == {}


# ---------------------------------------------------------------------------
# multi-pick-vocabulary -> JSON string
# ---------------------------------------------------------------------------
class TestNormalizeMultiPick:
    def test_list_values_become_json_string(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"], ["Toxoplasma", "Toxoplasma"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"organism": ["Plasmodium", "Toxoplasma"]})
        assert result["organism"] == json.dumps(["Plasmodium", "Toxoplasma"])

    def test_csv_string_becomes_json_string(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"], ["Toxoplasma", "Toxoplasma"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"organism": "Plasmodium,Toxoplasma"})
        assert result["organism"] == json.dumps(["Plasmodium", "Toxoplasma"])

    def test_json_array_string_normalized(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["Plasmodium", "Plasmodium"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"organism": '["Plasmodium"]'})
        assert result["organism"] == json.dumps(["Plasmodium"])

    def test_vocab_match_by_display(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                vocabulary=[["pf3d7", "Plasmodium falciparum 3D7"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"organism": ["Plasmodium falciparum 3D7"]})
        assert result["organism"] == json.dumps(["pf3d7"])

    def test_validates_min_count(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                min_selected=2,
                vocabulary=[["a", "a"]],
            )
        )
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"organism": ["a"]})
        assert "at least 2" in (exc_info.value.detail or "")

    def test_validates_max_count(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                max_selected=1,
                vocabulary=[["a", "a"], ["b", "b"]],
            )
        )
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"organism": ["a", "b"]})
        assert "at most 1" in (exc_info.value.detail or "")

    def test_none_value_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="organism",
                param_type="multi-pick-vocabulary",
                allow_empty=True,
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"organism": None})
        assert result["organism"] == ""

    def test_no_leaf_expansion_in_normalizer(self) -> None:
        """Normalizer does NOT expand selections to leaves, unlike canonicalizer."""
        vocab = {
            "data": {"term": "parent", "display": "Parent"},
            "children": [
                {"data": {"term": "leaf1", "display": "Leaf 1"}, "children": []},
                {"data": {"term": "leaf2", "display": "Leaf 2"}, "children": []},
            ],
        }
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=vocab,
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"p": ["Parent"]})
        # Normalizer keeps parent as-is (WDK handles expansion)
        assert result["p"] == json.dumps(["parent"])


# ---------------------------------------------------------------------------
# single-pick-vocabulary
# ---------------------------------------------------------------------------
class TestNormalizeSinglePick:
    def test_string_value(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                vocabulary=[["ring", "Ring"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"stage": "Ring"})
        assert result["stage"] == "ring"

    def test_multiple_values_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                vocabulary=[["a", "A"], ["b", "B"]],
            )
        )
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"stage": ["A", "B"]})
        assert "only one value" in (exc_info.value.detail or "")

    def test_empty_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                allow_empty=True,
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"stage": ""})
        assert result["stage"] == ""

    def test_empty_without_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="stage",
                param_type="single-pick-vocabulary",
                allow_empty=False,
            )
        )
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"stage": ""})
        assert "requires a value" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# scalar types
# ---------------------------------------------------------------------------
class TestNormalizeScalar:
    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_string_passthrough(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        result = n.normalize({"p": "value"})
        assert result["p"] == "value"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_integer_stringified(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        result = n.normalize({"p": 42})
        assert result["p"] == "42"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_bool_stringified(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        result = n.normalize({"p": True})
        assert result["p"] == "true"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_list_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": [1, 2]})
        assert "scalar" in (exc_info.value.detail or "")

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_dict_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": {"key": "val"}})
        assert "scalar" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# range types -> JSON string
# ---------------------------------------------------------------------------
class TestNormalizeRange:
    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_dict_becomes_json_string(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        result = n.normalize({"p": {"min": 1, "max": 10}})
        assert result["p"] == json.dumps({"min": 1, "max": 10})

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_list_pair_becomes_json_string(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        result = n.normalize({"p": [1, 10]})
        parsed = json.loads(result["p"])
        assert parsed == {"min": 1, "max": 10}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_invalid_raises(self, param_type: str) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type=param_type))
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": "invalid"})
        assert "must be a range" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# filter -> JSON string
# ---------------------------------------------------------------------------
class TestNormalizeFilter:
    def test_dict_becomes_json_string(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        n = _normalizer(spec)
        result = n.normalize({"p": {"filters": []}})
        assert result["p"] == json.dumps({"filters": []})

    def test_list_becomes_json_string(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        n = _normalizer(spec)
        result = n.normalize({"p": [{"field": "x"}]})
        assert result["p"] == json.dumps([{"field": "x"}])

    def test_string_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        n = _normalizer(spec)
        result = n.normalize({"p": "filter_val"})
        assert result["p"] == "filter_val"


# ---------------------------------------------------------------------------
# input-dataset
# ---------------------------------------------------------------------------
class TestNormalizeInputDataset:
    def test_single_list_item(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        n = _normalizer(spec)
        result = n.normalize({"p": ["dataset_1"]})
        assert result["p"] == "dataset_1"

    def test_multi_list_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": ["a", "b"]})
        assert "single value" in (exc_info.value.detail or "")

    def test_string_value(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        n = _normalizer(spec)
        result = n.normalize({"p": "dataset_1"})
        assert result["p"] == "dataset_1"


# ---------------------------------------------------------------------------
# unknown type passthrough
# ---------------------------------------------------------------------------
class TestNormalizeUnknownType:
    def test_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="unknown_type"))
        n = _normalizer(spec)
        result = n.normalize({"p": {"complex": "data"}})
        assert result["p"] == {"complex": "data"}


# ---------------------------------------------------------------------------
# Difference between normalizer and canonicalizer
# ---------------------------------------------------------------------------
class TestNormalizerVsCanonicalizerDifferences:
    """Verify the key differences in wire format between normalize and canonicalize."""

    def test_multi_pick_normalizer_returns_json_string(self) -> None:
        """Normalizer returns a JSON string for multi-pick (WDK wire format)."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                vocabulary=[["a", "a"], ["b", "b"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"p": ["a", "b"]})
        assert isinstance(result["p"], str)
        assert json.loads(result["p"]) == ["a", "b"]

    def test_range_normalizer_returns_json_string(self) -> None:
        """Normalizer returns a JSON string for ranges (WDK wire format)."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        n = _normalizer(spec)
        result = n.normalize({"p": {"min": 1, "max": 10}})
        assert isinstance(result["p"], str)
        assert json.loads(result["p"]) == {"min": 1, "max": 10}

    def test_filter_normalizer_returns_json_string(self) -> None:
        """Normalizer returns a JSON string for filters (WDK wire format)."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        n = _normalizer(spec)
        result = n.normalize({"p": {"filters": []}})
        assert isinstance(result["p"], str)
