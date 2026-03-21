"""Edge-case and bug-hunting tests for domain/research/citations.py and
cross-domain validation concerns."""

from pydantic import ValidationError

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    _slug_token,
    _suggest_tag,
    ensure_unique_citation_tags,
)

# ===========================================================================
# 1. _slug_token edge cases
# ===========================================================================


class TestSlugTokenEdgeCases:
    def test_unicode_stripped(self) -> None:
        """Non-alphanumeric unicode should be stripped."""
        result = _slug_token("hello-world!")
        assert result == "helloworld"

    def test_accented_chars_stripped(self) -> None:
        """Accented characters not in [a-z0-9] are stripped.

        Note: _slug_token uses re.sub(r'[^a-z0-9]+', '', ...) which strips
        non-ASCII characters like accented letters.
        """
        result = _slug_token("\u00e9t\u00e9")  # "ete" with accents
        assert result == "t"  # only 't' survives the regex, accents stripped

    def test_numbers_preserved(self) -> None:
        result = _slug_token("abc123")
        assert result == "abc123"

    def test_only_special_chars(self) -> None:
        result = _slug_token("!@#$%^&*()")
        assert result == ""

    def test_max_len_zero(self) -> None:
        result = _slug_token("hello", max_len=0)
        assert result == ""

    def test_max_len_one(self) -> None:
        result = _slug_token("hello", max_len=1)
        assert result == "h"

    def test_non_string_type(self) -> None:
        """Non-string input should return empty."""
        result = _slug_token(42)  # type: ignore[arg-type]
        assert result == ""


# ===========================================================================
# 2. _suggest_tag edge cases
# ===========================================================================


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


class TestSuggestCitationTagEdgeCases:
    def test_empty_authors_list(self) -> None:
        tag = _suggest_tag(_c(title="Title", authors=[], year=2020))
        # Empty authors list -> first_author is None -> falls to title
        assert tag == "title2020"

    def test_author_with_spaces_only(self) -> None:
        """Whitespace-only author name should not crash.

        BUG FIX: Previously crashed with IndexError because
        "   ".split(",")[0].split() returns [] and [0] was called on it.
        Fixed by checking parts list before indexing.
        """
        tag = _suggest_tag(_c(title="Title", authors=["   "], year=2020))
        # Whitespace author -> empty first_last -> falls to title-based tag
        assert tag == "title2020"

    def test_author_non_string_in_list_rejected(self) -> None:
        # Pydantic validates authors as list[str]; non-string elements are rejected
        with __import__("pytest").raises(ValidationError):
            _c(title="Title", authors=[42], year=2020)  # type: ignore[list-item]

    def test_no_title_no_authors_with_url(self) -> None:
        tag = _suggest_tag(
            Citation(id="test", source="web", title="", url="https://example.com/path")
        )
        assert isinstance(tag, str)
        assert len(tag) > 0

    def test_all_empty_fallback_to_source(self) -> None:
        tag = _suggest_tag(Citation(id="test", source="europepmc", title=""))
        assert tag == "europepmc"

    def test_title_with_only_special_chars(self) -> None:
        """Title that slugs to empty should fallback."""
        tag = _suggest_tag(_c(title="!@#$%"))
        # title.split()[0] = "!@#$%", _slug_token("!@#$%") = "" -> empty
        # title_slug = _slug_token("!@#$%", max_len=20) = "" -> empty
        # stable = _slug_token(None, max_len=20) = "" -> empty
        # return "" or str("web") = "web"
        assert tag == "web"


# ===========================================================================
# 3. ensure_unique_citation_tags edge cases
# ===========================================================================


class TestEnsureUniqueCitationTagsEdgeCases:
    def test_single_citation(self) -> None:
        citations = [{"tag": "smith2020"}]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "smith2020"

    def test_empty_list(self) -> None:
        citations: list[dict] = []
        ensure_unique_citation_tags(citations)
        assert citations == []

    def test_all_same_tags(self) -> None:
        citations = [{"tag": "x"} for _ in range(5)]
        ensure_unique_citation_tags(citations)
        tags = [c["tag"] for c in citations]
        assert len(set(tags)) == 5
        assert tags[0] == "x"
        assert tags[1] == "xa"
        assert tags[2] == "xb"
        assert tags[3] == "xc"
        assert tags[4] == "xd"

    def test_exactly_26_duplicates_uses_letters(self) -> None:
        """First 27 entries: first is plain, next 26 use a-z suffix."""
        citations = [{"tag": "x"} for _ in range(27)]
        ensure_unique_citation_tags(citations)
        tags = [c["tag"] for c in citations]
        assert tags[0] == "x"
        assert tags[1] == "xa"
        assert tags[26] == "xz"

    def test_27_duplicates_switches_to_numeric(self) -> None:
        """The 28th duplicate should use numeric suffix."""
        citations = [{"tag": "x"} for _ in range(28)]
        ensure_unique_citation_tags(citations)
        tags = [c["tag"] for c in citations]
        assert tags[0] == "x"
        assert tags[26] == "xz"
        assert tags[27] == "x_28"

    def test_none_tag_becomes_ref(self) -> None:
        citations = [{"tag": None}]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "ref"

    def test_missing_tag_key_becomes_ref(self) -> None:
        citations = [{}]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "ref"

    def test_non_dict_items_skipped(self) -> None:
        citations = [{"tag": "ok"}, "not a dict", 42, {"tag": "ok"}]  # type: ignore[list-item]
        ensure_unique_citation_tags(citations)  # type: ignore[arg-type]
        assert citations[0]["tag"] == "ok"
        assert citations[3]["tag"] == "oka"  # type: ignore[index]

    def test_tag_with_special_chars_slugified(self) -> None:
        """Tags are slugified via _slug_token during dedup check."""
        citations = [{"tag": "Hello World!"}]
        ensure_unique_citation_tags(citations)
        assert citations[0]["tag"] == "helloworld"

    def test_different_tags_preserved(self) -> None:
        citations = [{"tag": "alpha"}, {"tag": "beta"}, {"tag": "gamma"}]
        ensure_unique_citation_tags(citations)
        assert [c["tag"] for c in citations] == ["alpha", "beta", "gamma"]


# ===========================================================================
# 4. Citation dataclass edge cases
# ===========================================================================


class TestCitationEdgeCases:
    def test_minimal_citation(self) -> None:
        c = Citation(id="x", source="web", title="T")
        d = c.to_dict()
        assert d["id"] == "x"
        assert d["source"] == "web"
        assert d["title"] == "T"
        assert "tag" in d
        # All optional fields should be None
        assert d["url"] is None
        assert d["authors"] is None
        assert d["year"] is None
        assert d["doi"] is None
        assert d["pmid"] is None
        assert d["snippet"] is None
        assert d["accessedAt"] is None

    def test_citation_tag_generation(self) -> None:
        """Citation.to_dict() should generate a tag via _suggest_citation_tag."""
        c = Citation(
            id="x",
            source="pubmed",
            title="Test",
            authors=["Smith J"],
            year=2020,
        )
        d = c.to_dict()
        assert d["tag"] == "smith2020"

    def test_citation_immutable(self) -> None:
        """Citation is frozen Pydantic model."""
        c = Citation(id="x", source="web", title="T")
        with __import__("pytest").raises(ValidationError):
            c.title = "New"  # type: ignore[misc]


# ===========================================================================
# 5. Helper function edge cases
# ===========================================================================


class TestNewCitationIdEdgeCases:
    def test_different_prefixes(self) -> None:
        id1 = _new_citation_id("web")
        id2 = _new_citation_id("pubmed")
        assert id1.startswith("web_")
        assert id2.startswith("pubmed_")

    def test_empty_prefix(self) -> None:
        cid = _new_citation_id("")
        assert cid.startswith("_")

    def test_uniqueness_batch(self) -> None:
        ids = {_new_citation_id("test") for _ in range(1000)}
        assert len(ids) == 1000


class TestNowIsoEdgeCases:
    def test_returns_valid_iso(self) -> None:
        result = _now_iso()
        assert "T" in result
        # Should contain timezone info
        assert "+" in result or "Z" in result

    def test_successive_calls_ordered(self) -> None:
        """Two successive calls should produce ordered timestamps."""
        t1 = _now_iso()
        t2 = _now_iso()
        assert t1 <= t2
