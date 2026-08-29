from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.integrations.eda.models import (
    EdaFilter,
    EdaLongitudeRangeFilter,
    EdaMultiFilter,
    EdaStringSetFilter,
)

FILTER = TypeAdapter(EdaFilter)
FILTERS = TypeAdapter(list[EdaFilter])


def test_string_set_round_trips_the_wire_shape() -> None:
    raw = {
        "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
        "variableId": "VAR_035294d0",
        "type": "stringSet",
        "stringSet": ["P. berghei"],
    }
    parsed = FILTER.validate_python(raw)
    assert isinstance(parsed, EdaStringSetFilter)
    assert parsed.model_dump(by_alias=True, exclude_none=True) == raw


def test_an_empty_string_set_is_refused_before_the_wire() -> None:
    """The service answers 400 'String set filter: >0 strings must be specified'."""
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "stringSet",
                "stringSet": [],
            }
        )


def test_longitude_range_uses_left_and_right() -> None:
    parsed = FILTER.validate_python(
        {
            "entityId": "GAZ_00000448",
            "variableId": "OBI_0001621",
            "type": "longitudeRange",
            "left": 15.0,
            "right": 16.0,
        }
    )
    assert isinstance(parsed, EdaLongitudeRangeFilter)
    assert parsed.left == 15.0
    assert parsed.right == 16.0


def test_multi_filter_sub_filters_carry_no_entity_and_no_type() -> None:
    raw = {
        "entityId": "EUPATH_0000096",
        "variableId": "EUPATH_0000321",
        "type": "multiFilter",
        "operation": "union",
        "subFilters": [
            {"variableId": "EUPATH_0015135", "stringSet": ["Yes"]},
            {"variableId": "EUPATH_0033376", "stringSet": ["Yes"]},
        ],
    }
    parsed = FILTER.validate_python(raw)
    assert isinstance(parsed, EdaMultiFilter)
    assert parsed.operation == "union"
    assert parsed.model_dump(by_alias=True, exclude_none=True) == raw


def test_multi_filter_refuses_an_empty_sub_filter_list() -> None:
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "multiFilter",
                "operation": "union",
                "subFilters": [],
            }
        )


def test_multi_filter_refuses_an_operation_outside_the_two() -> None:
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "multiFilter",
                "operation": "xor",
                "subFilters": [{"variableId": "C", "stringSet": ["Yes"]}],
            }
        )


def test_string_prefix_set_is_refused() -> None:
    """Schema-present, source-present, wire-absent: the deployed build 422s it."""
    with pytest.raises(ValidationError):
        FILTER.validate_python(
            {
                "entityId": "E",
                "variableId": "V",
                "type": "stringPrefixSet",
                "prefixSet": ["ab"],
            }
        )


def test_an_extra_property_on_a_filter_is_dropped() -> None:
    parsed = FILTER.validate_python(
        {
            "entityId": "E",
            "variableId": "V",
            "type": "stringSet",
            "stringSet": ["yes"],
            "extraJunk": 1,
        }
    )
    assert "extraJunk" not in parsed.model_dump(by_alias=True)


def test_a_filter_array_serializes_as_a_bare_list() -> None:
    raw = [
        {
            "entityId": "E",
            "variableId": "V1",
            "type": "stringSet",
            "stringSet": ["a"],
        },
        {
            "entityId": "E",
            "variableId": "V2",
            "type": "numberRange",
            "min": 0.0,
            "max": 100.0,
        },
    ]
    parsed = FILTERS.validate_python(raw)
    assert FILTERS.dump_python(parsed, by_alias=True, exclude_none=True) == raw
