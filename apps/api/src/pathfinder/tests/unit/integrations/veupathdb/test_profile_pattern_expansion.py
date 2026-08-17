"""The wire layer expands a clade code to the species the census holds."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.platform.errors import AppError


def _term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


_TREE_PARAMS: list[WDKParameter] = [
    WDKStringParam(name="profile_pattern", is_visible=False),
    WDKStringParam(name="included_species", allow_empty_value=True),
    WDKStringParam(name="excluded_species", allow_empty_value=True),
    WDKEnumParam(
        name="phyletic_term_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _term("ALL", "Root"),
            _term("EUKA", "Eukaryota"),
            _term("MAMM", "Mammalia"),
            _term("hsap", "Homo sapiens REF"),
            _term("mmus", "Mus musculus"),
            _term("pfal", "Plasmodium falciparum 3D7"),
        ],
    ),
    WDKEnumParam(
        name="phyletic_indent_map",
        type="multi-pick-vocabulary",
        vocabulary=[
            _term("EUKA", "1"),
            _term("MAMM", "2"),
            _term("hsap", "3"),
            _term("mmus", "3"),
            _term("pfal", "2"),
        ],
    ),
]


def _empty_indent_map() -> WDKParameter:
    return WDKEnumParam(
        name="phyletic_indent_map", type="multi-pick-vocabulary", vocabulary=[]
    )


def _api(params: list[WDKParameter] | None = None) -> StrategyAPIBase:
    details = MagicMock()
    details.search_data.parameters = _TREE_PARAMS if params is None else params
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    return StrategyAPIBase(client)


class TestTheExpansion:
    async def test_a_clade_becomes_its_species(self) -> None:
        got = await _api()._expand_profile_pattern_groups(
            "transcript", "%MAMM:N%pfal:Y%"
        )

        assert got == "%hsap:N%mmus:N%pfal:Y%"

    async def test_an_explicit_species_overrides_its_clade(self) -> None:
        got = await _api()._expand_profile_pattern_groups(
            "transcript", "%MAMM:N%hsap:Y%"
        )

        assert got == "%hsap:Y%mmus:N%"

    async def test_species_codes_are_sorted_into_census_order(self) -> None:
        got = await _api()._expand_profile_pattern_groups(
            "transcript", "%pfal:Y%hsap:N%"
        )

        assert got == "%hsap:N%pfal:Y%"

    async def test_the_bare_wildcard_stands(self) -> None:
        assert await _api()._expand_profile_pattern_groups("transcript", "%") == "%"

    async def test_a_search_that_carries_no_tree_leaves_the_pattern_alone(self) -> None:
        got = await _api([])._expand_profile_pattern_groups("transcript", "%pfal:Y%")

        assert got == "%pfal:Y%"

    async def test_an_unreadable_tree_ships_the_pattern_sorted_and_unexpanded(
        self,
    ) -> None:
        # Without the depths a clade holds no species, so expanding would drop
        # the constraint instead of widening it.
        flat = [
            p if p.name != "phyletic_indent_map" else _empty_indent_map()
            for p in _TREE_PARAMS
        ]

        got = await _api(flat)._expand_profile_pattern_groups(
            "transcript", "%pfal:Y%MAMM:N%"
        )

        assert got == "%MAMM:N%pfal:Y%"


class TestTheGuard:
    async def test_the_published_default_is_refused(self) -> None:
        with pytest.raises(AppError) as err:
            await _api()._expand_profile_pattern_groups("transcript", "hsap=1T")

        assert err.value.status == 422

    async def test_an_unknown_code_is_refused(self) -> None:
        with pytest.raises(AppError) as err:
            await _api()._expand_profile_pattern_groups("transcript", "%zzzz:Y%")

        assert err.value.status == 422
        assert "zzzz" in str(err.value.detail)

    async def test_a_repeated_code_is_named(self) -> None:
        with pytest.raises(AppError) as err:
            await _api()._expand_profile_pattern_groups("transcript", "%hsap:Y%hsap:N%")

        assert err.value.status == 422
        assert "hsap" in str(err.value.detail)
        assert "census token" not in str(err.value.detail)

    def test_the_normalizer_refuses_a_repeated_code_too(self) -> None:
        # The expansion path is not the only way a pattern reaches the wire.
        with pytest.raises(AppError) as err:
            _api()._normalize_parameters({"profile_pattern": "%hsap:Y%hsap:N%"})

        assert err.value.status == 422
        assert "hsap" in str(err.value.detail)

    def test_the_normalizer_still_sorts_a_valid_pattern(self) -> None:
        got = _api()._normalize_parameters({"profile_pattern": "%pfal:Y%hsap:N%"})

        assert got["profile_pattern"] == "%hsap:N%pfal:Y%"
