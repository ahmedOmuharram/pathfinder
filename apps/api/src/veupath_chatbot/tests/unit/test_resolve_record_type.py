"""Unit tests for services.wdk.record_types.resolve_record_type."""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordType
from veupath_chatbot.services.wdk.record_types import resolve_record_type


def _rt(
    url_segment: str,
    full_name: str = "",
    display_name: str = "",
) -> WDKRecordType:
    """Build a WDKRecordType for testing."""
    return WDKRecordType(
        url_segment=url_segment,
        full_name=full_name,
        display_name=display_name,
    )


# -- Exact match (url_segment) ------------------------------------------------


class TestExactMatch:
    def test_url_segment_exact(self) -> None:
        result = resolve_record_type([_rt("gene"), _rt("transcript")], "gene")
        assert result == "gene"

    def test_dict_url_segment_exact(self) -> None:
        available = [_rt("gene", full_name="Gene", display_name="Genes")]
        assert resolve_record_type(available, "gene") == "gene"

    def test_full_name_exact(self) -> None:
        """Strategy 2: match on full_name when url_segment doesn't match."""
        available = [_rt("gene", full_name="GeneRecordClasses.GeneRecordClass")]
        assert (
            resolve_record_type(available, "GeneRecordClasses.GeneRecordClass")
            == "gene"
        )


# -- Case-insensitive matching ----------------------------------------------


class TestCaseInsensitive:
    def test_uppercase_input(self) -> None:
        result = resolve_record_type([_rt("gene"), _rt("transcript")], "GENE")
        assert result == "gene"

    def test_mixed_case_input(self) -> None:
        result = resolve_record_type([_rt("gene")], "GeNe")
        assert result == "gene"

    def test_dict_case_insensitive(self) -> None:
        available = [_rt("gene", full_name="Gene", display_name="Genes")]
        assert resolve_record_type(available, "GENE") == "gene"


# -- Whitespace trimming ---------------------------------------------------


class TestWhitespace:
    def test_leading_trailing_whitespace(self) -> None:
        result = resolve_record_type([_rt("gene")], "  gene  ")
        assert result == "gene"

    def test_whitespace_only_input_no_match(self) -> None:
        result = resolve_record_type([_rt("gene")], "   ")
        assert result is None


# -- Display name matching -------------------------------------------------


class TestDisplayName:
    def test_single_display_name_match(self) -> None:
        available = [
            _rt("gene", full_name="Gene", display_name="Genes"),
            _rt("transcript", full_name="Transcript", display_name="EST"),
        ]
        assert resolve_record_type(available, "Genes") == "gene"

    def test_ambiguous_display_name_returns_none(self) -> None:
        """Multiple record types with same displayName -> no match."""
        available = [
            _rt("gene", full_name="Gene", display_name="Records"),
            _rt("transcript", full_name="Transcript", display_name="Records"),
        ]
        assert resolve_record_type(available, "Records") is None

    def test_display_name_case_insensitive(self) -> None:
        available = [_rt("gene", full_name="Gene", display_name="Genes")]
        assert resolve_record_type(available, "genes") == "gene"


# -- Full name (strategy 2) ------------------------------------------------


class TestFullNameMatch:
    def test_match_by_full_name_when_url_segment_differs(self) -> None:
        """Strategy 2: match full_name field when url_segment doesn't match."""
        available = [_rt("gene", full_name="GeneRecord", display_name="Genes")]
        # "GeneRecord" doesn't match url_segment ("gene"), so strategy 1 fails.
        # Strategy 2 checks the full_name field.
        assert resolve_record_type(available, "GeneRecord") == "gene"


# -- Plural forms / partial input ------------------------------------------


class TestPluralAndPartial:
    def test_plural_s_via_display_name(self) -> None:
        """Plural form matches when it's the displayName."""
        available = [_rt("gene", full_name="Gene", display_name="Genes")]
        assert resolve_record_type(available, "Genes") == "gene"

    def test_partial_input_no_match(self) -> None:
        """Partial substrings do NOT match (strict equality only)."""
        result = resolve_record_type([_rt("gene"), _rt("transcript")], "gen")
        assert result is None


# -- No match scenarios ----------------------------------------------------


class TestNoMatch:
    def test_nonexistent_type_returns_none(self) -> None:
        result = resolve_record_type([_rt("gene"), _rt("transcript")], "nonexistent")
        assert result is None

    def test_empty_available_types(self) -> None:
        assert resolve_record_type([], "gene") is None

    def test_empty_input(self) -> None:
        assert resolve_record_type([_rt("gene")], "") is None


# -- Edge cases -----------------------------------------------------------


class TestEdgeCases:
    def test_empty_url_segment_skipped(self) -> None:
        """Record types with empty url_segment don't match anything."""
        result = resolve_record_type(
            [_rt("", display_name="Genes"), _rt("gene")], "gene"
        )
        assert result == "gene"

    def test_display_name_only_no_match_on_url_segment(self) -> None:
        """Can't match displayName via strategy 1 (url_segment only)."""
        available = [_rt("gene", display_name="Genes")]
        # "Genes" doesn't match url_segment "gene" via strategy 1
        # but matches via strategy 3 (display_name)
        assert resolve_record_type(available, "Genes") == "gene"

    def test_prefers_url_segment_over_full_name(self) -> None:
        available = [_rt("gene", full_name="GeneInternal")]
        assert resolve_record_type(available, "gene") == "gene"
