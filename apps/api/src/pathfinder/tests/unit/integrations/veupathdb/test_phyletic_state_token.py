"""A phyletic entry states presence or absence, and nothing else.

The census tokens are ``code:Y`` and ``code:N``. WDK matches the pattern with
SQL LIKE, so any other token simply fails to match and the search returns a
count rather than an error. The code half is already checked; the state half
was not, so a valid code with an invalid state passed through and emptied the
strategy in silence.
"""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.strategy_api.base import (
    _validate_phyletic_codes,
)
from pathfinder.platform.errors import AppError

_KNOWN = {"cpar", "tgon", "pfal", "apicomplexa"}


class TestAnInvalidStateIsRejected:
    def test_a_digit_state(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["cpar:0"], _KNOWN)

        assert "cpar:0" in str(err.value.detail)

    def test_the_message_names_the_two_valid_tokens(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["cpar:0"], _KNOWN)

        detail = str(err.value.detail)
        assert "Y" in detail
        assert "N" in detail

    def test_orthomcl_syntax(self) -> None:
        with pytest.raises(AppError):
            _validate_phyletic_codes(["cpar:1T"], _KNOWN)

    def test_a_lowercase_state(self) -> None:
        with pytest.raises(AppError):
            _validate_phyletic_codes(["cpar:y"], _KNOWN)

    def test_the_error_is_a_validation_error(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["cpar:0"], _KNOWN)

        assert err.value.status == 422


class TestValidEntriesPass:
    def test_present(self) -> None:
        _validate_phyletic_codes(["cpar:Y"], _KNOWN)

    def test_absent(self) -> None:
        _validate_phyletic_codes(["cpar:N"], _KNOWN)

    def test_several_entries(self) -> None:
        _validate_phyletic_codes(["cpar:N", "pfal:Y", "tgon:Y"], _KNOWN)

    def test_a_group_entry_keeps_its_quantifier(self) -> None:
        # Groups are expanded to leaves later; the state still has to be real.
        _validate_phyletic_codes(["apicomplexa:Y:all"], _KNOWN)

    def test_an_entry_with_no_state_is_left_to_the_code_check(self) -> None:
        _validate_phyletic_codes(["cpar"], _KNOWN)


class TestTheCodeCheckStillApplies:
    def test_an_unknown_code_is_rejected(self) -> None:
        with pytest.raises(AppError) as err:
            _validate_phyletic_codes(["zzzz:Y"], _KNOWN)

        assert "zzzz" in str(err.value.detail)
