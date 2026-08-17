"""A phyletic entry states presence or absence, and nothing else.

The census tokens are ``code:Y`` and ``code:N``. WDK matches the pattern with
SQL LIKE, so any other token simply fails to match and the search returns a
count rather than an error.
"""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.strategy_api.base import (
    _read_census,
    _validate_phyletic_codes,
)
from pathfinder.platform.errors import AppError

_KNOWN = {"cpar", "tgon", "pfal", "apicomplexa"}


class TestAnInvalidStateIsNotACensusPattern:
    @pytest.mark.parametrize(
        "pattern",
        ["%cpar:0%", "%cpar:1T%", "%cpar:y%", "%cpar:%", "%:Y%"],
    )
    def test_the_token_is_refused(self, pattern: str) -> None:
        assert _read_census(pattern).states is None

    def test_a_quantifier_is_no_longer_a_token(self) -> None:
        # Nothing writes a quantifier: the pattern is derived from the two
        # species lists, which push a clade down to its leaves.
        assert _read_census("%apicomplexa:Y:all%").states is None


class TestValidTokensPass:
    @pytest.mark.parametrize("pattern", ["%cpar:Y%", "%cpar:N%", "%cpar:N%pfal:Y%"])
    def test_presence_and_absence(self, pattern: str) -> None:
        assert _read_census(pattern).states is not None


class TestTheCodeCheck:
    def test_an_unknown_code_is_rejected(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["zzzz"], _KNOWN)

        assert "zzzz" in str(err.value.detail)

    def test_the_error_is_a_validation_error(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["zzzz"], _KNOWN)

        assert err.value.status == 422

    def test_known_codes_pass(self) -> None:
        _validate_phyletic_codes(["cpar", "pfal", "apicomplexa"], _KNOWN)
