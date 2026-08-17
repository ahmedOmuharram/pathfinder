"""A profile pattern is a census pattern or it is nothing.

The value is matched with SQL LIKE against a colon-joined census, so a string
that is not of that form matches nothing and WDK answers 200 with a count. The
published default is one such string, in another search's grammar, so it
reaches the query unexamined and returns an empty answer that reads as science.
"""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.strategy_api.base import (
    is_census_pattern,
)


class TestACensusPatternIsAccepted:
    @pytest.mark.parametrize(
        "pattern",
        ["%hsap:N%", "%cpar:N%", "%atum:Y%bant:Y%", "%pfal:Y%hsap:N%"],
    )
    def test_present_and_absent_tokens(self, pattern: str) -> None:
        assert is_census_pattern(pattern)

    def test_a_group_entry_with_a_quantifier(self) -> None:
        assert is_census_pattern("%apicomplexa:Y:all%")

    def test_the_bare_wildcard_is_a_pattern(self) -> None:
        # No constraint at all is expressible and means every profile.
        assert is_census_pattern("%")


class TestAnythingElseIsRefused:
    def test_the_published_default(self) -> None:
        # Valid in OrthoMCL's phyletic_expression grammar, not in this one.
        assert not is_census_pattern("hsap=1T")

    @pytest.mark.parametrize(
        "pattern",
        ["hsap>=1T", "hsap=0T", "not a pattern at all", ""],
    )
    def test_other_shapes(self, pattern: str) -> None:
        assert not is_census_pattern(pattern)

    def test_wrapped_but_not_a_census_token(self) -> None:
        assert not is_census_pattern("%hsap=1T%")

    def test_a_token_without_a_state(self) -> None:
        assert not is_census_pattern("%hsap%")
