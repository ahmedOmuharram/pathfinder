"""A quantity the request states must bind or come back to be read.

A numeric parameter's default is legitimate when the request says nothing about
a quantity. When the request states one and nothing bound it, taking the default
answers a question nobody asked and reports it as the user's intent, so the walk
reports the parameter unread instead.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.value_codec import to_wire
from pathfinder.services.catalog.param_dag import (
    OverrideMap,
    ParamFetcher,
    ResolvedParams,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent

_PCT = "min_expression_percentile"


def _numeric(name: str, default: str = "80", *, required: bool = True) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=required,
        is_visible=True,
        is_number=True,
        help="",
        value_format="",
        default_value=default,
    )


def _text(name: str, default: str = "") -> ParameterInfo:
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


def _only(*infos: ParameterInfo) -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return list(infos)

    return fetch_at


async def _resolve(
    text: str, *infos: ParameterInfo, overrides: OverrideMap | None = None
) -> ResolvedParams:
    return await resolve_params_with_intent(
        fetch_at=_only(*infos), intent=ParamIntent(text=text), overrides=overrides
    )


class TestAStatedQuantityIsReportedUnread:
    @pytest.mark.asyncio
    async def test_a_stated_quantity_left_null_is_reported_not_defaulted(self) -> None:
        resolved = await _resolve("top 10 percent, so percentile 90", _numeric(_PCT))

        assert resolved.unread == [_PCT]
        assert _PCT not in resolved.params

    @pytest.mark.asyncio
    async def test_it_is_reported_unresolved_and_is_not_a_question(self) -> None:
        # An open slot asks the user. This asks the caller to read the request it
        # already has, so it must not reach the user as a question.
        resolved = await _resolve("top 10 percent", _numeric(_PCT))

        assert resolved.unresolved_required == [_PCT]
        assert resolved.open_slots == []
        assert resolved.defaulted() == []

    @pytest.mark.asyncio
    async def test_an_optional_param_is_reported_too(self) -> None:
        # An optional param dropped here runs on the search's own default anyway,
        # so silence would lose the stated number just as quietly.
        resolved = await _resolve("top 10 percent", _numeric(_PCT, required=False))

        assert resolved.unread == [_PCT]
        assert _PCT not in resolved.params

    @pytest.mark.asyncio
    async def test_a_percent_sign(self) -> None:
        assert (await _resolve("top 10%", _numeric(_PCT))).unread == [_PCT]

    @pytest.mark.asyncio
    async def test_a_decimal_threshold(self) -> None:
        resolved = await _resolve(
            "adjusted p-value below 0.05", _numeric("adj_p_value")
        )

        assert resolved.unread == ["adj_p_value"]

    @pytest.mark.asyncio
    async def test_a_comparison(self) -> None:
        resolved = await _resolve("dN/dS <= 1.3", _numeric("dn_ds_ratio_upper"))

        assert resolved.unread == ["dn_ds_ratio_upper"]

    @pytest.mark.asyncio
    async def test_a_count(self) -> None:
        resolved = await _resolve("at least 2 peptides", _numeric("min_peptides"))

        assert resolved.unread == ["min_peptides"]


class TestTheStatedValueBinds:
    @pytest.mark.asyncio
    async def test_passing_the_value_leaves_nothing_unread(self) -> None:
        resolved = await _resolve(
            "top 10 percent, so percentile 90",
            _numeric(_PCT),
            overrides={_PCT: "90"},
        )

        assert resolved.unread == []
        assert to_wire(resolved.params[_PCT]) == "90"

    @pytest.mark.asyncio
    async def test_a_default_that_equals_the_stated_quantity_binds(self) -> None:
        resolved = await _resolve("percentile 90", _numeric(_PCT, "90"))

        assert resolved.unread == []
        assert to_wire(resolved.params[_PCT]) == "90"


class TestTheRequestStatesNoQuantity:
    @pytest.mark.asyncio
    async def test_plain_prose_keeps_the_default(self) -> None:
        resolved = await _resolve(
            "genes under purifying selection", _numeric("dn_ds_ratio_lower", "0")
        )

        assert resolved.unread == []
        assert to_wire(resolved.params["dn_ds_ratio_lower"]) == "0"

    @pytest.mark.asyncio
    async def test_empty_text_keeps_the_default(self) -> None:
        resolved = await _resolve("", _numeric("dn_ds_ratio_lower", "0"))

        assert resolved.unread == []
        assert to_wire(resolved.params["dn_ds_ratio_lower"]) == "0"

    @pytest.mark.asyncio
    async def test_a_number_that_names_a_thing_rather_than_a_quantity(self) -> None:
        # An accession is an identifier. Reading it as a threshold would hold the
        # default back on every domain search.
        resolved = await _resolve("InterPro domain PF00069", _numeric("min_peptides"))

        assert resolved.unread == []
        assert to_wire(resolved.params["min_peptides"]) == "80"

    @pytest.mark.asyncio
    async def test_a_gene_identifier(self) -> None:
        resolved = await _resolve("gene PF3D7_0100100", _numeric("min_peptides"))

        assert resolved.unread == []
        assert to_wire(resolved.params["min_peptides"]) == "80"


class TestSeveralNumericSlotsAreLeftAlone:
    """One number and several numeric params does not say which one it answers.

    Holding all of them back trades more correct defaults than it saves wrong
    ones, measured against the gold corpus.
    """

    @pytest.mark.asyncio
    async def test_two_unrelated_quantities_keep_their_defaults(self) -> None:
        ratio = _numeric("dn_ds_ratio_lower", "0")
        density = _numeric("snp_density_lower", "0")

        resolved = await _resolve("dN/dS <= 1.3", ratio, density)

        assert resolved.unread == []
        assert to_wire(resolved.params["dn_ds_ratio_lower"]) == "0"
        assert to_wire(resolved.params["snp_density_lower"]) == "0"

    @pytest.mark.asyncio
    async def test_a_numeric_slot_beside_a_text_param_is_still_held_back(self) -> None:
        resolved = await _resolve(
            "top 10 percent", _numeric(_PCT), _text("organism", "Plasmodium")
        )

        assert resolved.unread == [_PCT]

    @pytest.mark.asyncio
    async def test_a_sibling_with_no_default_does_not_count(self) -> None:
        resolved = await _resolve(
            "top 10 percent", _numeric(_PCT), _numeric("max_expression_percentile", "")
        )

        assert resolved.unread == [_PCT]


class TestOnlyNumericParamsAreAffected:
    @pytest.mark.asyncio
    async def test_a_text_param_is_never_held_back(self) -> None:
        # A free-text default is suppressed for its own reasons, and that opens a
        # slot for the user rather than reporting the param unread.
        resolved = await _resolve("top 10 percent", _text("text_expression", "kinase"))

        assert resolved.unread == []
        assert [slot.param_name for slot in resolved.open_slots] == ["text_expression"]

    @pytest.mark.asyncio
    async def test_a_numeric_param_with_no_default_is_a_question(self) -> None:
        resolved = await _resolve("top 10 percent", _numeric("min_peptides", ""))

        assert resolved.unread == []
        assert [slot.param_name for slot in resolved.open_slots] == ["min_peptides"]
