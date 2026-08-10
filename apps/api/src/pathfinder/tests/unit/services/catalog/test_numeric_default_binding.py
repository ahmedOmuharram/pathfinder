"""A numeric bound's initial value is a default, not a text example.

Measured on live WDK. `GenesBySnps` asks five required numeric params and WDK
ships an `initialDisplayValue` for every one:

    MinPercentMinorAlleles  0     occurrences_lower   0
    MinPercentIsolateCalls  20    snp_density_lower   0
    dn_ds_ratio_lower       0

WDK reports all of them as `type: "string"` with `isNumber: true`, so
`_is_free_text_query` -- which suppresses a default for a visible, required,
vocabulary-less string -- swallowed them all and escalated five Tier-3
questions instead. That guard exists for a real reason (`GenesByText` ships
`*reductase` as the *example* in its default, and inheriting it turns an
odorant-binding-protein search into a reductase search), but a number's
initial value is what PlasmoDB itself pre-fills, not an example.

That accounted for 5 of the 7 open slots on the drug-target strategy.
"""

from __future__ import annotations

from pathfinder.domain.parameters.values import StringValue
from pathfinder.services.catalog.param_dag import (
    ParameterInfo,
    _scalar_default,
    param_value_for,
)


def _numeric(name: str, default: str, *, is_number: bool = True) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=True,
        is_visible=True,
        is_number=is_number,
        help="",
        value_format="",
        default_value=default,
    )


def _free_text(name: str, default: str) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=True,
        is_visible=True,
        is_number=False,
        help="",
        value_format="",
        default_value=default,
    )


class TestNumericBoundsKeepTheirDefault:
    def test_a_zero_lower_bound_resolves(self) -> None:
        assert _scalar_default(_numeric("dn_ds_ratio_lower", "0")) == "0"

    def test_a_curated_non_zero_default_resolves(self) -> None:
        # WDK ships 20 here; asking the user is less faithful than using it.
        assert _scalar_default(_numeric("MinPercentIsolateCalls", "20")) == "20"

    def test_every_snp_bound_from_the_live_search_resolves(self) -> None:
        live = {
            "MinPercentMinorAlleles": "0",
            "MinPercentIsolateCalls": "20",
            "occurrences_lower": "0",
            "dn_ds_ratio_lower": "0",
            "snp_density_lower": "0",
        }

        unresolved = [
            name
            for name, default in live.items()
            if _scalar_default(_numeric(name, default)) is None
        ]

        assert unresolved == []


class TestFreeTextIsStillSuppressed:
    def test_a_text_query_example_is_not_inherited(self) -> None:
        # The GenesByText defect this guard exists for: *reductase is an
        # example in the form, and binding it rewrites the question.
        assert _scalar_default(_free_text("text_expression", "*reductase")) is None

    def test_a_number_flagged_search_text_is_still_suppressed(self) -> None:
        assert _scalar_default(_free_text("text_expression", "odorant")) is None


def test_the_resolved_value_is_a_string_param_value() -> None:
    info = _numeric("dn_ds_ratio_lower", "0")
    value = param_value_for(info, _scalar_default(info) or "")

    assert isinstance(value, StringValue)
    assert value.value == "0"
