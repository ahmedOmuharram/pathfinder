import pytest

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    StringValue,
    coerce_param_value,
)


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
