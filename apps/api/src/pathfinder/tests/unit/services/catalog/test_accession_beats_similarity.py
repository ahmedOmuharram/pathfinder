"""An accession the user named must beat a similarity score.

Observed on a real build. The goal said "InterPro domain PF00069", the
`domain_typeahead` vocabulary contains **`PF00069 : Pkinase`** verbatim among
its thousands entries, and the semantic matcher bound
`IPR000023 : Phosphofructokinase_dom` instead -- because that display text
contains the substring "kinase".

The strategy then searched phosphofructokinase rather than protein kinase and
returned **far fewer genes than intended**, with verification reporting success. A
wrong number that looks plausible is the worst failure this product can have.

The codebase already holds the principle, in `_rule_value` for organism and
contrast params: "a verbatim vocabulary term is much stronger evidence than a
similarity score". An accession is the strongest form of verbatim there is.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_intent import accession_in_text

_INTERPRO_VOCAB = [
    VocabOption(
        value="IPR000023 : Phosphofructokinase_dom", display="Phosphofructokinase"
    ),
    VocabOption(
        value="PF00069 : Pkinase", display="PF00069 : Pkinase Protein kinase domain"
    ),
    VocabOption(value="PF00433 : Pkinase_C", display="PF00433 : Pkinase_C"),
    VocabOption(value="PF07714 : PK_Tyr_Ser-Thr", display="Serine-threonine kinase"),
]


class TestAccessionWins:
    def test_a_pfam_accession_selects_its_own_entry(self) -> None:
        text = "kinases identified by InterPro domain PF00069 (Pkinase)"

        assert accession_in_text(_INTERPRO_VOCAB, text) == "PF00069 : Pkinase"

    def test_it_is_not_fooled_by_a_similar_display_name(self) -> None:
        # Phosphofructokinase contains "kinase"; the accession does not.
        text = "InterPro domain PF00069"

        assert accession_in_text(_INTERPRO_VOCAB, text) != (
            "IPR000023 : Phosphofructokinase_dom"
        )

    def test_a_go_accession_matches_despite_the_colon(self) -> None:
        vocab = [
            VocabOption(value="GO:0004672", display="protein kinase activity"),
            VocabOption(value="GO:0016301", display="kinase activity"),
        ]

        assert accession_in_text(vocab, "GO term GO:0016301") == "GO:0016301"

    def test_an_interpro_accession_matches(self) -> None:
        assert (
            accession_in_text(_INTERPRO_VOCAB, "domain IPR000023")
            == "IPR000023 : Phosphofructokinase_dom"
        )


class TestTruncatedVocabularies:
    """`allowed_values` is capped at 50 entries; `domain_typeahead` has thousands.

    `PF00069 : Pkinase` was not in the visible 50, so neither the model nor
    the matcher could see the entry the user named -- and
    `IPR000023 : Phosphofructokinase_dom` was. The full list lives in
    `vocab_leaves`, which is `exclude=True` and exists for exactly this kind
    of internal lookup, so matching must consult it too.
    """

    def test_it_finds_an_accession_only_present_in_the_leaves(self) -> None:
        visible = [
            VocabOption(value="IPR000023 : Phosphofructokinase_dom", display="x")
        ]
        hidden = [VocabOption(value="PF00069 : Pkinase", display="Protein kinase")]

        assert (
            accession_in_text(visible + hidden, "InterPro domain PF00069")
            == "PF00069 : Pkinase"
        )


class TestItStaysQuietWhenItShould:
    def test_no_accession_in_the_text_means_no_match(self) -> None:
        assert accession_in_text(_INTERPRO_VOCAB, "protein kinase domains") is None

    def test_an_accession_not_in_the_vocabulary_means_no_match(self) -> None:
        # Never invent: an unknown accession must fall through to the other
        # tiers rather than binding something adjacent.
        assert accession_in_text(_INTERPRO_VOCAB, "InterPro PF99999") is None

    def test_an_empty_vocabulary_is_safe(self) -> None:
        assert accession_in_text([], "PF00069") is None


@pytest.mark.parametrize(
    "text",
    ["pf00069", "PF00069", "Pf00069 : Pkinase"],
)
def test_accession_matching_ignores_case(text: str) -> None:
    assert accession_in_text(_INTERPRO_VOCAB, text) == "PF00069 : Pkinase"
