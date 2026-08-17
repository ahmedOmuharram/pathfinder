"""A value nobody chose is reported as one.

WDK demands hidden required parameters and the model cannot see them, so
PathFinder supplies their declared defaults. On 182 of plasmodb's 325 transcript
searches that is at least one parameter, and a default carries no promise of
returning rows. The fill is therefore named rather than adopted silently.
"""

from __future__ import annotations

from pathfinder.domain.parameters.specs import (
    ParamSpecNormalized,
    fill_hidden_required_defaults,
    filled_hidden_defaults,
)
from pathfinder.domain.parameters.values import SinglePickValue


def _spec(
    name: str,
    *,
    visible: bool,
    default: str | None,
    allow_empty: bool = False,
) -> ParamSpecNormalized:
    return ParamSpecNormalized(
        name=name,
        param_type="string",
        is_visible=visible,
        allow_empty_value=allow_empty,
        initial_display_value=default,
    )


_SPECS = {
    "organism": _spec("organism", visible=True, default="Pf3D7"),
    "channel": _spec("channel", visible=False, default="Channel 1"),
    "profile_pattern": _spec("profile_pattern", visible=False, default="hsap=1T"),
}


class TestTheFillIsNamed:
    def test_a_hidden_default_is_reported(self) -> None:
        assert filled_hidden_defaults(_SPECS, {}) == ["channel", "profile_pattern"]

    def test_a_value_the_caller_supplied_is_not_reported(self) -> None:
        supplied = {"profile_pattern": SinglePickValue(value="%hsap:N%pfal:Y%")}

        assert filled_hidden_defaults(_SPECS, supplied) == ["channel"]

    def test_a_visible_parameter_is_never_reported(self) -> None:
        # A visible default is the model's to see and choose.
        assert "organism" not in filled_hidden_defaults(_SPECS, {})

    def test_nothing_to_fill_reports_nothing(self) -> None:
        supplied = {
            "channel": SinglePickValue(value="Channel 1"),
            "profile_pattern": SinglePickValue(value="%pfal:Y%"),
        }

        assert filled_hidden_defaults(_SPECS, supplied) == []


class TestItAgreesWithTheFill:
    def test_every_reported_name_was_actually_filled(self) -> None:
        filled = fill_hidden_required_defaults(_SPECS, {})

        for name in filled_hidden_defaults(_SPECS, {}):
            assert name in filled

    def test_the_report_matches_what_the_fill_added(self) -> None:
        before = {"channel": SinglePickValue(value="Channel 2")}
        filled = fill_hidden_required_defaults(_SPECS, before)

        added = sorted(set(filled) - set(before))
        assert added == filled_hidden_defaults(_SPECS, before)

    def test_a_hidden_param_with_no_default_is_not_reported(self) -> None:
        specs = {"secret": _spec("secret", visible=False, default=None)}

        assert filled_hidden_defaults(specs, {}) == []

    def test_a_hidden_param_that_allows_empty_is_not_reported(self) -> None:
        specs = {
            "opt": _spec("opt", visible=False, default="x", allow_empty=True),
        }

        assert filled_hidden_defaults(specs, {}) == []
