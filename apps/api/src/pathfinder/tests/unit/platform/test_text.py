"""Truncation that a reader can tell apart from a short sentence.

Observed in UAT, in Settings -> Memory -> Strategies: "... gametocyte
expression data from bo" — a raw slice, cut mid-word, with nothing marking it
as cut. Every truncation in the app goes through this one helper so the
sentence ends on a word and says it was cut.
"""

from pathfinder.platform.text import truncate_on_word_boundary


def test_short_text_is_returned_unchanged() -> None:
    assert truncate_on_word_boundary("conserved male gametocyte markers", 80) == (
        "conserved male gametocyte markers"
    )


def test_text_at_the_limit_is_returned_unchanged() -> None:
    assert truncate_on_word_boundary("abcde", 5) == "abcde"


def test_truncation_ends_on_a_word_and_is_marked() -> None:
    source = (
        "Which Plasmodium falciparum genes are conserved male gametocyte "
        "markers, supported by gametocyte expression data from both sexes?"
    )
    out = truncate_on_word_boundary(source, 120)

    assert out.endswith("...")
    assert len(out) <= 120
    assert out == (
        "Which Plasmodium falciparum genes are conserved male gametocyte "
        "markers, supported by gametocyte expression data from..."
    )


def test_no_dangling_space_before_the_marker() -> None:
    assert truncate_on_word_boundary("alpha beta gamma", 12) == "alpha..."


def test_trailing_punctuation_is_dropped_with_the_cut_word() -> None:
    assert truncate_on_word_boundary("alpha, beta gamma", 13) == "alpha,..."


def test_a_single_unbreakable_token_is_hard_cut() -> None:
    """One long identifier has no word boundary — cut it rather than overflow."""
    out = truncate_on_word_boundary("PF3D7_" + "0" * 200, 20)

    assert len(out) == 20
    assert out.endswith("...")


def test_empty_text_stays_empty() -> None:
    assert truncate_on_word_boundary("", 40) == ""


def test_limit_smaller_than_the_marker_yields_a_hard_cut() -> None:
    assert truncate_on_word_boundary("alpha beta", 2) == "al"
