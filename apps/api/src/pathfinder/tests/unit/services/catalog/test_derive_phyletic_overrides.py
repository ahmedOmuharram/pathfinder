"""The two species lists are the proposal; the three parameter values are derived."""

from __future__ import annotations

from pathfinder.domain.parameters.phyletic import PhyleticBinding
from pathfinder.domain.parameters.wdk_vocab import VocabOption, WDKVocabTerm
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_phyletic import (
    PhyleticNoSelection,
    PhyleticUnresolvedProposal,
    derive_phyletic_overrides,
    is_phyletic_sheet,
)


def _term(code: str, display: str) -> WDKVocabTerm:
    return WDKVocabTerm((code, display, None))


def _phyletic_params() -> list[WDKParameter]:
    return [
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


def _ordinary_params() -> list[WDKParameter]:
    return [
        WDKStringParam(name="text_expression"),
        WDKStringParam(name="included_species", allow_empty_value=True),
    ]


class TestABindingIsDerived:
    def test_a_label_and_a_code_bind_the_three_values(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {
                "included_species": "Plasmodium falciparum 3D7",
                "excluded_species": ["hsap"],
            },
        )

        assert got == PhyleticBinding(
            profile_pattern="%hsap:N%pfal:Y%",
            included_species="pfal",
            excluded_species="hsap",
        )

    def test_a_clade_expands_in_the_pattern_and_stays_a_code_in_the_list(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {"included_species": "pfal", "excluded_species": "Mammalia"},
        )

        assert got == PhyleticBinding(
            profile_pattern="%hsap:N%mmus:N%pfal:Y%",
            included_species="pfal",
            excluded_species="MAMM",
        )

    def test_one_list_alone_leaves_the_other_empty(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(), {"excluded_species": "hsap"}
        )

        assert got == PhyleticBinding(
            profile_pattern="%hsap:N%",
            included_species="n/a",
            excluded_species="hsap",
        )


class TestAnEmptySelection:
    """Two empty lists state no criterion, and the bare wildcard hides that.

    The pattern would bind, the search would run, and it would answer with every
    gene of the chosen organisms as though the phyletic question was asked.
    """

    def test_both_lists_null(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {"included_species": None, "excluded_species": None},
        )

        assert isinstance(got, PhyleticNoSelection)

    def test_both_lists_holding_the_empty_marker(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {"included_species": "n/a", "excluded_species": []},
        )

        assert isinstance(got, PhyleticNoSelection)

    def test_neither_list_was_named(self) -> None:
        """Omitting both lists leaves the hidden pattern to its default, which is
        the same empty criterion the two empty lists state."""
        got = derive_phyletic_overrides(_phyletic_params(), {"organism": ["Pf3D7"]})

        assert isinstance(got, PhyleticNoSelection)


class TestNothingIsDerived:
    def test_a_search_that_is_not_phyletic(self) -> None:
        assert (
            derive_phyletic_overrides(_ordinary_params(), {"included_species": "pfal"})
            is None
        )

    def test_a_search_that_is_not_phyletic_and_names_no_list(self) -> None:
        assert (
            derive_phyletic_overrides(_ordinary_params(), {"text_expression": "kinase"})
            is None
        )


class TestAnUnresolvedProposal:
    def test_an_unknown_species_names_the_nearest_entries(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {"included_species": "Plasmodium falciparum", "excluded_species": "hsap"},
        )

        assert isinstance(got, PhyleticUnresolvedProposal)
        assert got.unresolved.included_unknown == ["Plasmodium falciparum"]
        assert "Plasmodium falciparum 3D7" in got.nearest

    def test_the_nearest_list_is_short_enough_to_read(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(), {"excluded_species": "Nosema"}
        )

        assert isinstance(got, PhyleticUnresolvedProposal)
        assert got.unresolved.excluded_unknown == ["Nosema"]
        assert 0 < len(got.nearest) <= 5

    def test_a_code_in_both_lists_is_a_conflict(self) -> None:
        got = derive_phyletic_overrides(
            _phyletic_params(),
            {"included_species": "pfal, hsap", "excluded_species": "hsap"},
        )

        assert isinstance(got, PhyleticUnresolvedProposal)
        assert got.unresolved.conflicts == ["hsap"]


def _info(name: str, *, visible: bool = True) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=False,
        is_visible=visible,
        help="",
        value_format="",
        vocab_leaves=[VocabOption(value="pfal", display="Plasmodium falciparum 3D7")],
    )


_PHYLETIC_SHEET = [
    _info("profile_pattern", visible=False),
    _info("included_species"),
    _info("excluded_species"),
    _info("organism"),
]


class TestTheSheetSignature:
    """The two structural maps never reach the sheet, so the other three name it.

    The proposals do not enter the signature: a phyletic search that names no
    list still owes a species selection.
    """

    def test_a_phyletic_sheet(self) -> None:
        assert is_phyletic_sheet(_PHYLETIC_SHEET)

    def test_an_ordinary_sheet(self) -> None:
        assert not is_phyletic_sheet([_info("included_species"), _info("organism")])
