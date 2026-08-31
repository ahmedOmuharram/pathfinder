import pytest

from pathfinder.domain.parameters.value_codec import (
    coerce_context_values,
    coerce_param_value,
    param_value_from_raw,
)
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberRangeValue,
    NumberValue,
    SinglePickValue,
    StringValue,
)


def test_coerce_context_values_by_shape() -> None:
    out = coerce_context_values(
        {
            "profileset_generic": "SRP047470 ... DESeq",
            "samples": ["Adult_female", "Adult_male"],
            "typed": {"type": "string", "value": "x"},
        }
    )
    assert out["profileset_generic"] == SinglePickValue(value="SRP047470 ... DESeq")
    assert out["samples"] == MultiPickValue(values=["Adult_female", "Adult_male"])
    assert out["typed"] == StringValue(value="x")


def test_coerce_context_values_passes_instances() -> None:
    out = coerce_context_values({"p": SinglePickValue(value="v")})
    assert out["p"] == SinglePickValue(value="v")


def test_from_raw_string_scalar() -> None:
    v = param_value_from_raw("odorant binding protein", "string")
    assert isinstance(v, StringValue)
    assert v.value == "odorant binding protein"


def test_from_raw_number_accepts_int_and_str() -> None:
    assert param_value_from_raw(2, "number") == NumberValue(value=2.0)
    assert param_value_from_raw("2", "number") == NumberValue(value=2.0)


def test_from_raw_single_pick() -> None:
    v = param_value_from_raw("Aedes aegypti", "single-pick-vocabulary")
    assert isinstance(v, SinglePickValue)
    assert v.value == "Aedes aegypti"


def test_from_raw_multi_pick_scalar_and_list() -> None:
    assert param_value_from_raw("InterPro", "multi-pick-vocabulary") == MultiPickValue(
        values=["InterPro"]
    )
    assert param_value_from_raw(
        ["InterPro", "product"], "multi-pick-vocabulary"
    ) == MultiPickValue(values=["InterPro", "product"])


def test_from_raw_passes_through_already_typed() -> None:
    v = param_value_from_raw({"type": "string", "value": "x"}, "string")
    assert isinstance(v, StringValue)
    assert v.value == "x"


def test_from_raw_number_range_from_dict() -> None:
    v = param_value_from_raw({"min": 1, "max": 5}, "number-range")
    assert isinstance(v, NumberRangeValue)
    assert (v.min, v.max) == (1.0, 5.0)


def test_coerce_identity_returns_same_value() -> None:
    v = StringValue(value="x")
    assert coerce_param_value(v, "string") is v


def test_coerce_integer_number_to_string() -> None:
    out = coerce_param_value(NumberValue(value=2.0), "string")
    assert out.type == "string"
    assert out.value == "2"


def test_coerce_float_number_to_string() -> None:
    out = coerce_param_value(NumberValue(value=1.5), "string")
    assert out.type == "string"
    assert out.value == "1.5"


def test_coerce_numeric_string_to_number() -> None:
    out = coerce_param_value(StringValue(value="1.5"), "number")
    assert out.type == "number"
    assert out.value == 1.5


def test_coerce_string_to_single_pick() -> None:
    out = coerce_param_value(StringValue(value="Pf3D7"), "single-pick-vocabulary")
    assert out.type == "single-pick-vocabulary"
    assert out.value == "Pf3D7"


def test_coerce_rejects_multipick_to_string() -> None:
    with pytest.raises(ValueError, match="not valid"):
        coerce_param_value(MultiPickValue(values=["a"]), "string")


def test_coerce_rejects_scalar_to_range() -> None:
    with pytest.raises(ValueError, match="not valid"):
        coerce_param_value(NumberValue(value=1.0), "number-range")
