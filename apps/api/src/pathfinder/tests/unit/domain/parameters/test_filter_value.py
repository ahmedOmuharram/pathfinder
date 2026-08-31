"""FilterValue emits exactly the authoritative wdk-client ``BaseFilter`` keys.

Source of truth: VEuPathDB/web-monorepo wdk-client
``Components/AttributeFilter/Types.ts`` — ``BaseFilter`` = {field, type,
isRange, includeUnknown, value}; and the live plasmodb param spec, whose
filter ``initialDisplayValue`` is ``{"filters":[]}`` (include all).
"""

from __future__ import annotations

import json

from pathfinder.domain.parameters.value_codec import param_value_from_raw
from pathfinder.domain.parameters.values import FilterTermClause, FilterValue


def test_empty_filter_is_include_all() -> None:
    assert FilterValue().to_wire() == '{"filters": []}'
    assert json.loads(FilterValue().to_wire()) == {"filters": []}


def test_clause_emits_authoritative_basefilter_keys() -> None:
    clause = FilterTermClause(
        field="Sample type", type="string", is_range=False, value=["culture", "blood"]
    )
    wire = json.loads(FilterValue(filters=[clause]).to_wire())
    assert wire == {
        "filters": [
            {
                "field": "Sample type",
                "type": "string",
                "isRange": False,
                "includeUnknown": False,
                "value": ["culture", "blood"],
            }
        ]
    }


def test_parse_drops_noise_keys_keeps_canonical() -> None:
    raw = {
        "filters": [
            {
                "field": "Country",
                "type": "string",
                "isRange": False,
                "includeUnknown": True,
                "value": ["India"],
                "fieldDisplayName": "Country",
            }
        ]
    }
    fv = param_value_from_raw(raw, "filter")
    assert isinstance(fv, FilterValue)
    clause = fv.filters[0]
    assert clause.field == "Country"
    assert clause.include_unknown is True
    assert "fieldDisplayName" not in json.loads(fv.to_wire())["filters"][0]
