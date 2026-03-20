"""Tests for services.gene_lookup.organism -- organism matching and normalization."""

from typing import ClassVar

import pytest

from veupath_chatbot.services.gene_lookup.organism import (
    normalize_organism,
    score_organism_match,
    suggest_organisms,
)

# ---------------------------------------------------------------------------
# score_organism_match
# ---------------------------------------------------------------------------


class TestScoreOrganismMatch:
    """Tests for the fuzzy organism scorer."""

    def test_exact_match_returns_1(self) -> None:
        assert (
            score_organism_match(
                "Plasmodium falciparum 3D7", "Plasmodium falciparum 3D7"
            )
            == 1.0
        )

    def test_case_insensitive_exact_match(self) -> None:
        assert (
            score_organism_match(
                "plasmodium falciparum 3d7", "Plasmodium falciparum 3D7"
            )
            == 1.0
        )

    def test_empty_query_returns_0(self) -> None:
        assert score_organism_match("", "Plasmodium falciparum 3D7") == 0.0

    def test_empty_organism_returns_0(self) -> None:
        assert score_organism_match("falciparum", "") == 0.0

    def test_both_empty_returns_0(self) -> None:
        assert score_organism_match("", "") == 0.0

    def test_whitespace_only_returns_0(self) -> None:
        assert score_organism_match("   ", "   ") == 0.0

    def test_substring_match(self) -> None:
        score = score_organism_match("falciparum", "Plasmodium falciparum 3D7")
        assert score == 0.85

    def test_genus_abbreviation_p_dot_falciparum(self) -> None:
        score = score_organism_match("P. falciparum", "Plasmodium falciparum 3D7")
        assert score == 0.80

    def test_genus_abbreviation_no_dot(self) -> None:
        score = score_organism_match("p falciparum", "Plasmodium falciparum 3D7")
        assert score == 0.80

    def test_organism_code_compact(self) -> None:
        # "pf3d7" => genus initial P + species initial F + strain "3d7"
        score = score_organism_match("pf3d7", "Plasmodium falciparum 3D7")
        assert score == 0.75

    def test_organism_code_with_trailing_star(self) -> None:
        score = score_organism_match("pf3d7*", "Plasmodium falciparum 3D7")
        assert score == 0.75

    def test_organism_code_slightly_longer(self) -> None:
        # Compact + up to 2 extra chars
        score = score_organism_match("pf3d7xx", "Plasmodium falciparum 3D7")
        assert score == 0.72

    def test_organism_code_underscore_prefix(self) -> None:
        # "pf3d7_something" => split on _, prefix "pf3d7" matches compact
        score = score_organism_match("pf3d7_001", "Plasmodium falciparum 3D7")
        assert score == 0.72

    def test_organism_code_underscore_prefix_slightly_long(self) -> None:
        score = score_organism_match("pf3d7ab_001", "Plasmodium falciparum 3D7")
        assert score == 0.68

    def test_token_subset_match(self) -> None:
        # All query tokens are present in organism tokens
        score = score_organism_match("falciparum 3D7", "Plasmodium falciparum 3D7")
        assert score == pytest.approx(0.85)  # actually substring match

    def test_token_subset_no_substring(self) -> None:
        # "Plasmodium 3D7" is not a substring of "Plasmodium falciparum 3D7"
        # but tokens {plasmodium, 3d7} are a subset of {plasmodium, falciparum, 3d7}
        score = score_organism_match("Plasmodium 3D7", "Plasmodium falciparum 3D7")
        assert score == 0.65

    def test_partial_token_match(self) -> None:
        # "falci" is a substring of "falciparum", so all(any(qt in ot ...)) passes
        score = score_organism_match("falci", "Plasmodium falciparum 3D7")
        # "falci" is a substring of the whole organism string too -> 0.85
        assert score == 0.85

    def test_no_match_at_all(self) -> None:
        score = score_organism_match("zzz_no_match", "Plasmodium falciparum 3D7")
        assert score == 0.0

    def test_whitespace_stripping(self) -> None:
        score = score_organism_match("  falciparum  ", "  Plasmodium falciparum 3D7  ")
        assert score == 0.85


# ---------------------------------------------------------------------------
# suggest_organisms
# ---------------------------------------------------------------------------


class TestSuggestOrganisms:
    AVAILABLE: ClassVar[list] = [
        "Plasmodium falciparum 3D7",
        "Plasmodium vivax P01",
        "Toxoplasma gondii ME49",
        "Cryptosporidium parvum Iowa II",
    ]

    def test_empty_query_returns_empty(self) -> None:
        assert suggest_organisms("", self.AVAILABLE) == []

    def test_empty_available_returns_empty(self) -> None:
        assert suggest_organisms("falciparum", []) == []

    def test_exact_match_returns_one(self) -> None:
        result = suggest_organisms("Plasmodium falciparum 3D7", self.AVAILABLE)
        assert result == ["Plasmodium falciparum 3D7"]

    def test_genus_abbreviation_suggests_multiple(self) -> None:
        result = suggest_organisms("P. falciparum", self.AVAILABLE)
        assert "Plasmodium falciparum 3D7" in result

    def test_max_suggestions_respected(self) -> None:
        result = suggest_organisms("Plasmodium", self.AVAILABLE, max_suggestions=1)
        assert len(result) <= 1

    def test_min_score_filters_low_matches(self) -> None:
        result = suggest_organisms("zzz", self.AVAILABLE, min_score=0.40)
        assert result == []

    def test_ordered_by_score_descending(self) -> None:
        # "falciparum" matches "Plasmodium falciparum 3D7" (0.85) but not others as well
        result = suggest_organisms("falciparum", self.AVAILABLE)
        assert result[0] == "Plasmodium falciparum 3D7"

    def test_multiple_matches(self) -> None:
        # "Plasmodium" is a substring of both Plasmodium species
        result = suggest_organisms("Plasmodium", self.AVAILABLE)
        assert len(result) >= 2
        assert all("Plasmodium" in r for r in result)


# ---------------------------------------------------------------------------
# normalize_organism
# ---------------------------------------------------------------------------


class TestNormalizeOrganism:
    def test_plain_string(self) -> None:
        assert (
            normalize_organism("Plasmodium falciparum 3D7")
            == "Plasmodium falciparum 3D7"
        )

    def test_empty_string(self) -> None:
        assert normalize_organism("") == ""

    def test_none_value(self) -> None:
        # The function does `strip_html_tags(raw or "")`, so None-ish works
        assert normalize_organism("") == ""

    def test_html_tags_stripped(self) -> None:
        assert (
            normalize_organism("<em>Plasmodium</em> falciparum")
            == "Plasmodium falciparum"
        )

    def test_json_array_format(self) -> None:
        assert (
            normalize_organism('["Plasmodium falciparum 3D7"]')
            == "Plasmodium falciparum 3D7"
        )

    def test_json_array_with_multiple_elements_returns_first(self) -> None:
        result = normalize_organism(
            '["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]'
        )
        assert result == "Plasmodium falciparum 3D7"

    def test_json_array_empty_falls_through(self) -> None:
        result = normalize_organism("[]")
        assert result == "[]"

    def test_invalid_json_returns_raw(self) -> None:
        result = normalize_organism("[broken json")
        assert result == "[broken json"

    def test_whitespace_stripped(self) -> None:
        assert (
            normalize_organism("  Plasmodium falciparum 3D7  ")
            == "Plasmodium falciparum 3D7"
        )

    def test_html_inside_json_array(self) -> None:
        result = normalize_organism('["<em>Plasmodium</em> falciparum 3D7"]')
        assert result == "Plasmodium falciparum 3D7"
