"""The parameter type enumeration, and the direction of drift PathFinder notices.

``JsonKeys`` declares eleven ``*_PARAM_TYPE`` constants and ``wdk-client``'s
``Parameter`` union is the same eleven. ``displayType`` is a separate axis.
"""

from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import ValidationError as PydanticValidationError

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.parameters.value_codec import (
    _SCALAR_KINDS,
    _SCALAR_VALUE_BY_KIND,
    _WIRE_BUILDERS,
    as_param_kind,
    from_wire,
)
from pathfinder.domain.parameters.values import MultiPickValue, ParamKind
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse

_THE_ELEVEN = frozenset(
    {
        "string",
        "number",
        "number-range",
        "date",
        "date-range",
        "timestamp",
        "single-pick-vocabulary",
        "multi-pick-vocabulary",
        "filter",
        "input-dataset",
        "input-step",
    }
)


def _genes_by_location() -> WDKSearchResponse:
    return WDKSearchResponse.model_validate(
        load_recorded("search_genes_by_location").json_body()
    )


class TestWdkParam001ElevenTypes:
    def test_wdk_param_001_param_kind_is_exactly_the_eleven(self) -> None:
        assert frozenset(get_args(ParamKind)) == _THE_ELEVEN

    def test_wdk_param_001_display_type_is_a_separate_axis(self) -> None:
        # organismSinglePick is a multi-pick parameter drawn as a select.
        search = _genes_by_location()
        params = {p.name: p for p in search.search_data.parameters or []}

        assert params["organismSinglePick"].type == "multi-pick-vocabulary"
        assert params["organismSinglePick"].display_type == "select"

    def test_wdk_param_001_a_select_multi_pick_still_sends_a_list(self) -> None:
        # Branching on displayType to decide whether to send a list is wrong here.
        search = _genes_by_location()
        params = {p.name: p for p in search.search_data.parameters or []}
        kind = as_param_kind(params["organismSinglePick"].type)

        value = from_wire(kind, json.dumps(["Plasmodium falciparum 3D7"]))

        assert value == MultiPickValue(values=["Plasmodium falciparum 3D7"])

    def test_wdk_param_001_every_declared_type_is_one_of_the_eleven(self) -> None:
        search = _genes_by_location()

        declared = {p.type for p in search.search_data.parameters or []}

        assert declared <= _THE_ELEVEN


class TestWdkMap001DriftIsNoticedInBothDirections:
    def test_wdk_map_001_a_twelfth_kind_is_refused_by_name(self) -> None:
        with pytest.raises(PydanticValidationError):
            as_param_kind("gene-list")

    def test_wdk_map_001_a_twelfth_kind_has_no_wire_form(self) -> None:
        # `_wire_payload` falls through for an unknown kind; the union refuses it.
        with pytest.raises(PydanticValidationError):
            from_wire("gene-list", "anything")  # type: ignore[arg-type]

    def test_wdk_map_001_every_kind_has_a_way_to_build_a_value(self) -> None:
        # Removing a member is caught by mypy over these three maps; adding one
        # is caught here.
        covered = (
            frozenset(_WIRE_BUILDERS) | _SCALAR_KINDS | frozenset(_SCALAR_VALUE_BY_KIND)
        )

        assert covered == _THE_ELEVEN

    def test_wdk_map_001_every_kind_round_trips_from_a_wire_string(self) -> None:
        wire_by_kind: dict[str, str] = {
            "string": "kinase",
            "number": "42",
            "number-range": '{"min": 1, "max": 2}',
            "date": "2026-01-01",
            "date-range": '{"min": "2026-01-01", "max": "2026-12-31"}',
            "timestamp": "1766000000000",
            "single-pick-vocabulary": "Gene",
            "multi-pick-vocabulary": '["product"]',
            "filter": '{"filters": []}',
            "input-dataset": "558341",
            "input-step": "440085983",
        }

        assert frozenset(wire_by_kind) == _THE_ELEVEN
        for kind, wire in wire_by_kind.items():
            assert from_wire(as_param_kind(kind), wire).type == kind
