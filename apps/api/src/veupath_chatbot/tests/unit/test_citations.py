"""Tests for citation domain types and utilities."""

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    _slug_token,
    _suggest_tag,
    ensure_unique_citation_tags,
)

# ---------------------------------------------------------------------------
# _slug_token
# ---------------------------------------------------------------------------


class TestSlugToken:
    def test_basic_slug(self) -> None:
        assert _slug_token("Hello World!") == "helloworld"

    def test_truncates_to_max_len(self) -> None:
        result = _slug_token("abcdefghijklmnopqrstuvwxyz", max_len=5)
        assert result == "abcde"

    def test_none_input(self) -> None:
        assert _slug_token(None) == ""

    def test_empty_string(self) -> None:
        assert _slug_token("") == ""

    def test_whitespace_only(self) -> None:
        assert _slug_token("   ") == ""

    def test_strips_non_alphanumeric(self) -> None:
        assert _slug_token("hello-world_123!") == "helloworld123"


# ---------------------------------------------------------------------------
# _suggest_tag
# ---------------------------------------------------------------------------


def _c(
    title: str = "",
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    pmid: str | None = None,
) -> Citation:
    """Build a minimal Citation for _suggest_tag tests."""
    return Citation(
        id="test",
        source="web",
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        pmid=pmid,
    )


class TestSuggestCitationTag:
    def test_author_and_year(self) -> None:
        tag = _suggest_tag(_c(title="Some Paper", authors=["Smith, John"], year=2020))
        assert tag == "smith2020"

    def test_author_no_year(self) -> None:
        tag = _suggest_tag(_c(title="Some Paper", authors=["Smith, John"]))
        assert tag == "smith"

    def test_title_first_word_with_year(self) -> None:
        tag = _suggest_tag(_c(title="Malaria treatment overview", year=2021))
        assert tag == "malaria2021"

    def test_title_slug_fallback(self) -> None:
        tag = _suggest_tag(_c(title="Malaria"))
        assert tag == "malaria"

    def test_doi_fallback(self) -> None:
        tag = _suggest_tag(_c(doi="10.1234/abc"))
        assert tag == "101234abc"

    def test_pmid_fallback(self) -> None:
        tag = _suggest_tag(_c(pmid="12345678"))
        assert tag == "12345678"

    def test_source_fallback(self) -> None:
        tag = _suggest_tag(Citation(id="test", source="web", title=""))
        assert tag == "web"


# ---------------------------------------------------------------------------
# ensure_unique_citation_tags
# ---------------------------------------------------------------------------


class TestEnsureUniqueCitationTags:
    def test_no_duplicates_unchanged(self) -> None:
        citations = [
            {"tag": "smith2020"},
            {"tag": "jones2021"},
        ]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "smith2020"
        assert citations[1]["tag"] == "jones2021"

    def test_duplicate_tags_get_suffixes(self) -> None:
        citations = [
            {"tag": "smith2020"},
            {"tag": "smith2020"},
            {"tag": "smith2020"},
        ]
        ensure_unique_citation_tags(citations)
        tags = [c["tag"] for c in citations]
        assert len(set(tags)) == 3
        assert tags[0] == "smith2020"
        assert tags[1] == "smith2020a"
        assert tags[2] == "smith2020b"

    def test_empty_tag_becomes_ref(self) -> None:
        citations = [{"tag": ""}]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "ref"

    def test_many_duplicates_use_numeric_suffix(self) -> None:
        # More than 26 duplicates should use numeric suffixes
        citations = [{"tag": "x"} for _ in range(30)]
        ensure_unique_citation_tags(citations)
        tags = [c["tag"] for c in citations]
        assert len(set(tags)) == 30  # all unique

    def test_skips_non_dicts(self) -> None:
        citations = [{"tag": "ok"}, "not a dict", {"tag": "ok"}]  # type: ignore[list-item]
        ensure_unique_citation_tags(citations)  # type: ignore[arg-type]
        assert citations[0]["tag"] == "ok"
        assert citations[2]["tag"] == "oka"  # type: ignore[index]


# ---------------------------------------------------------------------------
# Citation dataclass
# ---------------------------------------------------------------------------


class TestCitation:
    def test_tag_computed_from_author_and_year(self) -> None:
        c = Citation(
            id="x", source="pubmed", title="Test", authors=["Smith J"], year=2020
        )
        assert c.tag == "smith2020"

    def test_tag_falls_back_to_title_word(self) -> None:
        c = Citation(id="x", source="web", title="Kinase signaling")
        assert c.tag == "kinase"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestNewCitationId:
    def test_format(self) -> None:
        cid = _new_citation_id("test")
        assert cid.startswith("test_")
        assert len(cid) == len("test_") + 12

    def test_uniqueness(self) -> None:
        ids = {_new_citation_id("x") for _ in range(100)}
        assert len(ids) == 100


class TestNowIso:
    def test_returns_iso_string(self) -> None:
        result = _now_iso()
        assert "T" in result
        assert "+" in result or "Z" in result
