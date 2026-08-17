"""A vocabulary value is matched by term, by label, or by its leading accession."""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import VocabOption, match_exact_option

_PFAM = [
    VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
    VocabOption(value="PF00569 : ZZ", display="PF00569 : ZZ"),
    VocabOption(value="PF00169 : PH", display="PF00169 : PH"),
]

_EC = [
    VocabOption(value="2.7.1.1", display="2.7.1.1"),
    VocabOption(value="2.7.11.1", display="2.7.11.1"),
]


def test_a_term_matches_itself() -> None:
    assert match_exact_option(_PFAM, "PF00069 : Pkinase") == "PF00069 : Pkinase"


def test_an_accession_names_the_one_entry_that_carries_it() -> None:
    assert match_exact_option(_PFAM, "PF00069") == "PF00069 : Pkinase"


def test_an_accession_is_matched_ignoring_case() -> None:
    assert match_exact_option(_PFAM, "pf00069") == "PF00069 : Pkinase"


def test_a_prefix_of_an_accession_matches_nothing() -> None:
    assert match_exact_option(_EC, "2.7") is None


def test_a_value_holding_a_colon_is_not_split() -> None:
    options = [VocabOption(value="GO:0016301", display="kinase activity")]

    assert match_exact_option(options, "GO:0016301") == "GO:0016301"


def test_an_accession_two_entries_share_matches_nothing() -> None:
    options = [
        VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
        VocabOption(value="PF00069 : Pkinase_2", display="PF00069 : Pkinase_2"),
    ]

    assert match_exact_option(options, "PF00069") is None


def test_an_exact_label_wins_over_another_entrys_accession() -> None:
    options = [
        VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
        VocabOption(value="IPR000719", display="PF00069"),
    ]

    assert match_exact_option(options, "PF00069") == "IPR000719"


def test_a_leading_word_that_is_not_an_accession_matches_nothing() -> None:
    options = [VocabOption(value="Plasmodium falciparum 3D7", display="P. falciparum")]

    assert match_exact_option(options, "Plasmodium") is None
