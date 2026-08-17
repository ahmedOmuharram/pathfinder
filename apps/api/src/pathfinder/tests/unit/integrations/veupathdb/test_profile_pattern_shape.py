"""A profile pattern is a census pattern or it is nothing.

The value is matched with SQL LIKE against a colon-joined census, so a string
that is not of that form matches nothing and WDK answers 200 with a count. The
published default is one such string, in another search's grammar, so it
reaches the query unexamined and returns an empty answer that reads as science.
"""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.strategy_api.base import _read_census


class TestACensusPatternIsRead:
    @pytest.mark.parametrize(
        "pattern",
        ["%hsap:N%", "%cpar:N%", "%atum:Y%bant:Y%", "%pfal:Y%hsap:N%"],
    )
    def test_present_and_absent_tokens(self, pattern: str) -> None:
        assert _read_census(pattern).states is not None

    def test_the_bare_wildcard_is_a_pattern(self) -> None:
        # No constraint at all is expressible and means every profile.
        assert _read_census("%").states == {}

    def test_each_token_yields_its_state(self) -> None:
        assert _read_census("%pfal:Y%hsap:N%").states == {
            "pfal": "include",
            "hsap": "exclude",
        }


class TestAnythingElseIsRefused:
    def test_the_published_default(self) -> None:
        # Valid in OrthoMCL's phyletic_expression grammar, not in this one.
        assert _read_census("hsap=1T").states is None

    @pytest.mark.parametrize(
        "pattern",
        ["hsap>=1T", "hsap=0T", "not a pattern at all", ""],
    )
    def test_other_shapes(self, pattern: str) -> None:
        assert _read_census(pattern).states is None

    def test_wrapped_but_not_a_census_token(self) -> None:
        assert _read_census("%hsap=1T%").states is None

    def test_a_token_without_a_state(self) -> None:
        assert _read_census("%hsap%").states is None

    def test_a_quantified_group_token(self) -> None:
        # The pattern is derived from the two species lists, which expand a
        # clade to its leaves; no producer writes a quantifier.
        assert _read_census("%apicomplexa:Y:all%").states is None

    def test_a_code_that_states_two_states(self) -> None:
        # One species has one state in the census, so this matches nothing.
        assert _read_census("%hsap:Y%hsap:N%").states is None

    def test_the_repeated_code_is_reported(self) -> None:
        assert _read_census("%hsap:Y%hsap:N%").repeated_code == "hsap"

    def test_another_shape_reports_no_repeated_code(self) -> None:
        assert _read_census("hsap=1T").repeated_code is None
