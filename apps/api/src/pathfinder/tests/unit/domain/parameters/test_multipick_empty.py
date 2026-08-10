"""A multi-pick parameter must be able to say "nothing selected".

``MultiPickValue`` used to require at least one value, so an empty selection
had no valid representation. Callers degraded it to the literal string "[]",
which then reached vocabulary matching and was rejected with
"Parameter 'phyletic_indent_map' does not accept '[]'" - a 422 on a parameter
whose own spec sets allowEmptyValue=true.

Whether an empty selection is ALLOWED is a per-parameter question answered by
the spec (``validate_multi_count``), not something the value type should
decide for every parameter at once.
"""

import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from pathfinder.domain.parameters.values import (
    _PARAM_VALUE_ADAPTER,
    MultiPickValue,
)


def test_empty_selection_is_representable() -> None:
    assert MultiPickValue(values=[]).values == []


def test_empty_selection_serializes_to_an_empty_json_array() -> None:
    # WDK's wire form for "nothing selected".
    assert MultiPickValue(values=[]).to_wire() == "[]"


def test_empty_selection_decodes_to_an_empty_list() -> None:
    # Not ["[]"], which is what vocabulary matching used to choke on.
    assert MultiPickValue(values=[]).to_decoded() == []


def test_empty_selection_round_trips_through_parse() -> None:
    raw = json.loads(MultiPickValue(values=[]).model_dump_json(by_alias=True))
    parsed = _PARAM_VALUE_ADAPTER.validate_python(raw)
    assert isinstance(parsed, MultiPickValue)
    assert parsed.values == []


def test_non_empty_selection_still_works() -> None:
    value = MultiPickValue(values=["bant", "bsub"])
    assert value.to_decoded() == ["bant", "bsub"]
    assert json.loads(value.to_wire()) == ["bant", "bsub"]


def test_values_must_still_be_strings() -> None:
    # Relaxing emptiness must not relax the element type.
    with pytest.raises(PydanticValidationError):
        MultiPickValue(values=[{"nope": 1}])  # type: ignore[list-item]
