"""One ranker answers every did-you-mean: value prefixes first, then similarity."""

from __future__ import annotations

from pathfinder.domain.parameters.wdk_vocab import VocabOption, nearest_entries

_DOMAINS = [
    VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
    VocabOption(value="PF00569 : ZZ", display="PF00569 : ZZ"),
    VocabOption(value="PF00169 : PH", display="PF00169 : PH"),
    VocabOption(value="PF00560 : LRR_1", display="PF00560 : LRR_1"),
    VocabOption(value="PF00006 : ATP-synt_ab", display="PF00006 : ATP-synt_ab"),
]

_SPECIES = [
    VocabOption(value="EUKA", display="Eukaryota"),
    VocabOption(value="MAMM", display="Mammalia"),
    VocabOption(value="hsap", display="Homo sapiens REF"),
    VocabOption(value="mmus", display="Mus musculus"),
    VocabOption(value="pfal", display="Plasmodium falciparum 3D7"),
]


class TestPrefixMatchesLead:
    def test_the_entries_the_proposal_starts_come_first(self) -> None:
        got = nearest_entries(_DOMAINS, "PF0006", 5)

        assert got[0] == "PF00069 : Pkinase"
        assert got.index("PF00069 : Pkinase") < got.index("PF00569 : ZZ")

    def test_a_prefix_match_ignores_case(self) -> None:
        got = nearest_entries(_SPECIES, "PFAL", 5)

        assert got[0] == "pfal"

    def test_prefix_matches_alone_fill_the_limit(self) -> None:
        got = nearest_entries(_DOMAINS, "PF00", 2)

        assert got == ["PF00069 : Pkinase", "PF00569 : ZZ"]


class TestSimilarityFillsTheRest:
    def test_a_label_is_reachable_when_no_value_matches(self) -> None:
        got = nearest_entries(_SPECIES, "Plasmodium falciparum", 5)

        assert "Plasmodium falciparum 3D7" in got

    def test_the_result_is_capped_at_the_limit(self) -> None:
        got = nearest_entries(_SPECIES, "Nosema", 3)

        assert len(got) == 3

    def test_an_entry_listed_by_prefix_is_not_listed_again_as_its_label(self) -> None:
        """One entry occupies one place in the answer. A prefix hit on the value
        takes its label out of the similarity pool."""
        got = nearest_entries(_SPECIES, "pfal", 5)

        assert got[0] == "pfal"
        assert "Plasmodium falciparum 3D7" not in got

    def test_a_value_is_never_repeated_by_its_own_label(self) -> None:
        options = [VocabOption(value="yes", display="yes")]

        got = nearest_entries(options, "false", 5)

        assert got == ["yes"]

    def test_an_empty_label_is_not_an_entry(self) -> None:
        options = [VocabOption(value="text_expression", display="")]

        got = nearest_entries(options, "text_expresion", 5)

        assert got == ["text_expression"]
