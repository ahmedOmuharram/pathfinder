"""Unit tests for the generic JSON codec (to_json / from_json).

Covers snake_to_camel, field rounding, nested dataclasses, Union/Optional,
Literal passthrough, list/tuple/dict coercion, and edge cases.
"""

from dataclasses import dataclass, field

from veupath_chatbot.services.experiment.types import (
    OperatorComparison,
    OperatorVariant,
    ParameterSensitivity,
    ParameterSweepPoint,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)
from veupath_chatbot.services.experiment.types.json_codec import (
    _snake_to_camel,
    from_json,
    to_json,
)

# ---------------------------------------------------------------------------
# Test dataclasses (not part of production code)
# ---------------------------------------------------------------------------


@dataclass
class _Inner:
    value: int = 0
    label: str = ""


@dataclass
class _Outer:
    name: str = ""
    inner: _Inner | None = None
    items: list[_Inner] = field(default_factory=list)


@dataclass
class _WithRounding:
    default_round: float = 0.0
    custom_round: float = field(default=0.0, metadata={"round": 2})
    no_round: float = field(default=0.0, metadata={"round": None})


@dataclass
class _WithOptional:
    required_field: str = ""
    optional_str: str | None = None
    optional_inner: _Inner | None = None


@dataclass
class _WithDict:
    mapping: dict[str, int] = field(default_factory=dict)
    int_keys: dict[int, str] = field(default_factory=dict)


@dataclass
class _WithTuple:
    pair: tuple[int, str] = (0, "")


@dataclass
class _WithDefaults:
    name: str = "default_name"
    count: int = 42


# ---------------------------------------------------------------------------
# _snake_to_camel
# ---------------------------------------------------------------------------


class TestSnakeToCamel:
    def test_single_word(self) -> None:
        assert _snake_to_camel("name") == "name"

    def test_two_words(self) -> None:
        assert _snake_to_camel("first_name") == "firstName"

    def test_three_words(self) -> None:
        assert _snake_to_camel("some_long_name") == "someLongName"

    def test_already_camel(self) -> None:
        """No underscores means passthrough."""
        assert _snake_to_camel("firstName") == "firstName"

    def test_leading_underscore(self) -> None:
        # Edge case -- leading underscore makes first part empty
        result = _snake_to_camel("_private")
        assert result == "Private"

    def test_empty_string(self) -> None:
        assert _snake_to_camel("") == ""

    def test_single_char_parts(self) -> None:
        assert _snake_to_camel("a_b_c") == "aBC"


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------


class TestToJson:
    def test_none(self) -> None:
        assert to_json(None) is None

    def test_string(self) -> None:
        assert to_json("hello") == "hello"

    def test_int(self) -> None:
        assert to_json(42) == 42

    def test_bool(self) -> None:
        assert to_json(True) is True

    def test_float_default_rounding(self) -> None:
        result = to_json(3.14159265)
        assert result == 3.1416

    def test_float_custom_rounding(self) -> None:
        obj = _WithRounding(
            default_round=3.14159265,
            custom_round=3.14159265,
            no_round=3.14159265,
        )
        j = to_json(obj)
        assert j["defaultRound"] == 3.1416  # default 4 decimals
        assert j["customRound"] == 3.14  # custom 2 decimals
        assert j["noRound"] == 3.14159265  # no rounding

    def test_simple_dataclass(self) -> None:
        obj = _Inner(value=5, label="test")
        j = to_json(obj)
        assert j == {"value": 5, "label": "test"}

    def test_nested_dataclass(self) -> None:
        obj = _Outer(name="parent", inner=_Inner(value=10, label="child"))
        j = to_json(obj)
        assert j["name"] == "parent"
        assert j["inner"]["value"] == 10
        assert j["inner"]["label"] == "child"

    def test_none_nested(self) -> None:
        obj = _Outer(name="parent", inner=None)
        j = to_json(obj)
        assert j["inner"] is None

    def test_list_of_dataclasses(self) -> None:
        obj = _Outer(
            name="parent",
            items=[_Inner(value=1), _Inner(value=2)],
        )
        j = to_json(obj)
        assert len(j["items"]) == 2
        assert j["items"][0]["value"] == 1
        assert j["items"][1]["value"] == 2

    def test_list_of_scalars(self) -> None:
        assert to_json([1, 2, 3]) == [1, 2, 3]

    def test_tuple_serialized_as_list(self) -> None:
        assert to_json((1, 2, 3)) == [1, 2, 3]

    def test_dict_keys_stringified(self) -> None:
        assert to_json({1: "a", 2: "b"}) == {"1": "a", "2": "b"}

    def test_nested_dict_values(self) -> None:
        obj = _WithDict(mapping={"a": 1, "b": 2})
        j = to_json(obj)
        assert j["mapping"] == {"a": 1, "b": 2}

    def test_camel_case_keys(self) -> None:
        obj = _WithOptional(required_field="yes", optional_str="maybe")
        j = to_json(obj)
        assert "requiredField" in j
        assert "optionalStr" in j


# ---------------------------------------------------------------------------
# from_json
# ---------------------------------------------------------------------------


class TestFromJson:
    def test_simple_dataclass(self) -> None:
        data = {"value": 5, "label": "test"}
        obj = from_json(data, _Inner)
        assert obj.value == 5
        assert obj.label == "test"

    def test_camel_case_keys(self) -> None:
        data = {"requiredField": "yes", "optionalStr": "maybe"}
        obj = from_json(data, _WithOptional)
        assert obj.required_field == "yes"
        assert obj.optional_str == "maybe"

    def test_missing_optional_uses_default(self) -> None:
        data = {"requiredField": "yes"}
        obj = from_json(data, _WithOptional)
        assert obj.required_field == "yes"
        assert obj.optional_str is None

    def test_missing_fields_use_defaults(self) -> None:
        data = {}
        obj = from_json(data, _WithDefaults)
        assert obj.name == "default_name"
        assert obj.count == 42

    def test_nested_dataclass(self) -> None:
        data = {
            "name": "parent",
            "inner": {"value": 10, "label": "child"},
            "items": [],
        }
        obj = from_json(data, _Outer)
        assert obj.name == "parent"
        assert obj.inner is not None
        assert obj.inner.value == 10
        assert obj.inner.label == "child"

    def test_none_nested(self) -> None:
        data = {"name": "parent", "inner": None, "items": []}
        obj = from_json(data, _Outer)
        assert obj.inner is None

    def test_list_of_dataclasses(self) -> None:
        data = {
            "name": "parent",
            "items": [
                {"value": 1, "label": "a"},
                {"value": 2, "label": "b"},
            ],
        }
        obj = from_json(data, _Outer)
        assert len(obj.items) == 2
        assert obj.items[0].value == 1
        assert obj.items[1].label == "b"

    def test_dict_with_string_keys(self) -> None:
        data = {"mapping": {"a": 1, "b": 2}, "intKeys": {}}
        obj = from_json(data, _WithDict)
        assert obj.mapping == {"a": 1, "b": 2}

    def test_dict_with_int_keys(self) -> None:
        data = {"mapping": {}, "intKeys": {"1": "a", "2": "b"}}
        obj = from_json(data, _WithDict)
        assert obj.int_keys == {1: "a", 2: "b"}

    def test_tuple_from_list(self) -> None:
        data = {"pair": [42, "hello"]}
        obj = from_json(data, _WithTuple)
        assert obj.pair == (42, "hello")


# ---------------------------------------------------------------------------
# Roundtrip tests
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_simple_roundtrip(self) -> None:
        original = _Inner(value=99, label="roundtrip")
        j = to_json(original)
        restored = from_json(j, _Inner)
        assert restored.value == 99
        assert restored.label == "roundtrip"

    def test_nested_roundtrip(self) -> None:
        original = _Outer(
            name="root",
            inner=_Inner(value=7, label="nested"),
            items=[_Inner(value=1), _Inner(value=2)],
        )
        j = to_json(original)
        restored = from_json(j, _Outer)
        assert restored.name == "root"
        assert restored.inner is not None
        assert restored.inner.value == 7
        assert len(restored.items) == 2

    def test_optional_none_roundtrip(self) -> None:
        original = _WithOptional(required_field="yes")
        j = to_json(original)
        restored = from_json(j, _WithOptional)
        assert restored.required_field == "yes"
        assert restored.optional_str is None
        assert restored.optional_inner is None


# ---------------------------------------------------------------------------
# Step analysis type roundtrip
# ---------------------------------------------------------------------------


class TestStepAnalysisTypesRoundtrip:
    """Ensure the real step analysis dataclasses survive to_json/from_json roundtrip."""

    def test_step_evaluation_roundtrip(self) -> None:
        original = StepEvaluation(
            step_id="s1",
            search_name="GenesByTaxon",
            display_name="Taxon Search",
            result_count=500,
            positive_hits=8,
            positive_total=10,
            negative_hits=3,
            negative_total=20,
            recall=0.8,
            false_positive_rate=0.15,
            captured_positive_ids=["g1", "g2"],
            tp_movement=-2,
            fp_movement=1,
            fn_movement=2,
        )
        j = to_json(original)
        restored = from_json(j, StepEvaluation)
        assert restored.step_id == "s1"
        assert restored.positive_hits == 8
        assert restored.tp_movement == -2
        assert restored.captured_positive_ids == ["g1", "g2"]

    def test_step_contribution_roundtrip(self) -> None:
        original = StepContribution(
            step_id="s1",
            search_name="Search1",
            baseline_recall=0.8,
            ablated_recall=0.6,
            recall_delta=-0.2,
            baseline_fpr=0.1,
            ablated_fpr=0.05,
            fpr_delta=-0.05,
            verdict="essential",
            narrative="Removing this step drops recall.",
        )
        j = to_json(original)
        restored = from_json(j, StepContribution)
        assert restored.verdict == "essential"
        assert restored.recall_delta == -0.2
        assert restored.narrative == "Removing this step drops recall."

    def test_operator_comparison_roundtrip(self) -> None:
        original = OperatorComparison(
            combine_node_id="c1",
            current_operator="INTERSECT",
            variants=[
                OperatorVariant(
                    operator="INTERSECT",
                    positive_hits=8,
                    negative_hits=3,
                    total_results=100,
                    recall=0.8,
                    false_positive_rate=0.15,
                    f1_score=0.82,
                ),
                OperatorVariant(
                    operator="UNION",
                    positive_hits=10,
                    negative_hits=8,
                    total_results=200,
                    recall=1.0,
                    false_positive_rate=0.4,
                    f1_score=0.75,
                ),
            ],
            recommendation="Current operator is optimal.",
            recommended_operator="INTERSECT",
        )
        j = to_json(original)
        restored = from_json(j, OperatorComparison)
        assert restored.combine_node_id == "c1"
        assert len(restored.variants) == 2
        assert restored.variants[0].operator == "INTERSECT"
        assert restored.variants[1].recall == 1.0

    def test_parameter_sensitivity_roundtrip(self) -> None:
        original = ParameterSensitivity(
            step_id="s1",
            param_name="evalue",
            current_value=1e-5,
            sweep_points=[
                ParameterSweepPoint(
                    value=1e-10,
                    positive_hits=5,
                    negative_hits=0,
                    total_results=50,
                    recall=0.5,
                    fpr=0.0,
                    f1=0.67,
                ),
            ],
            recommended_value=1e-10,
            recommendation="Change evalue to 1e-10.",
        )
        j = to_json(original)
        restored = from_json(j, ParameterSensitivity)
        assert restored.param_name == "evalue"
        assert len(restored.sweep_points) == 1
        assert restored.sweep_points[0].positive_hits == 5

    def test_step_analysis_result_roundtrip(self) -> None:
        original = StepAnalysisResult()
        j = to_json(original)
        restored = from_json(j, StepAnalysisResult)
        assert restored.step_evaluations == []
        assert restored.operator_comparisons == []
        assert restored.step_contributions == []
        assert restored.parameter_sensitivities == []
