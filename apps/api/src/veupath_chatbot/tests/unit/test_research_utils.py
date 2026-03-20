"""Tests for research utility functions."""

import httpx
import respx

from veupath_chatbot.domain.research.citations import LiteratureFilters
from veupath_chatbot.services.research.utils import (
    LiteratureItemContext,
    candidate_queries,
    decode_ddg_redirect,
    dedupe_key,
    fallback_ratio,
    fetch_page_summary,
    fuzzy_score,
    limit_authors,
    list_str,
    looks_blocked,
    norm_for_match,
    norm_text,
    passes_filters,
    rerank_score,
    strip_tags,
    truncate_text,
)

# ---------------------------------------------------------------------------
# norm_text
# ---------------------------------------------------------------------------


class TestNormText:
    def test_strips_and_lowercases(self) -> None:
        assert norm_text("  Hello World  ") == "hello world"

    def test_none_returns_empty(self) -> None:
        assert norm_text(None) == ""

    def test_empty_string(self) -> None:
        assert norm_text("") == ""


# ---------------------------------------------------------------------------
# list_str
# ---------------------------------------------------------------------------


class TestListStr:
    def test_converts_list_values_to_strings(self) -> None:
        assert list_str([1, "two", 3]) == ["1", "two", "3"]

    def test_skips_none_values(self) -> None:
        assert list_str(["a", None, "b"]) == ["a", "b"]

    def test_non_list_returns_empty(self) -> None:
        assert list_str("not a list") == []
        assert list_str(42) == []
        assert list_str(None) == []

    def test_empty_list(self) -> None:
        assert list_str([]) == []


# ---------------------------------------------------------------------------
# limit_authors
# ---------------------------------------------------------------------------


class TestLimitAuthors:
    def test_truncates_and_adds_et_al(self) -> None:
        result = limit_authors(["Alice", "Bob", "Charlie"], 2)
        assert result == ["Alice", "Bob", "et al."]

    def test_no_truncation_when_within_limit(self) -> None:
        result = limit_authors(["Alice", "Bob"], 5)
        assert result == ["Alice", "Bob"]

    def test_exact_limit(self) -> None:
        result = limit_authors(["Alice", "Bob"], 2)
        assert result == ["Alice", "Bob"]

    def test_negative_one_means_no_limit(self) -> None:
        authors = ["A", "B", "C", "D", "E"]
        result = limit_authors(authors, -1)
        assert result == authors

    def test_zero_max_returns_et_al(self) -> None:
        result = limit_authors(["Alice"], 0)
        assert result == ["et al."]

    def test_none_input(self) -> None:
        assert limit_authors(None, 3) is None

    def test_empty_list_returns_none(self) -> None:
        assert limit_authors([], 3) is None

    def test_filters_none_and_blank_authors(self) -> None:
        result = limit_authors(["Alice", None, "", "Bob"], 5)
        assert result == ["Alice", "Bob"]

    def test_all_none_returns_none(self) -> None:
        assert limit_authors([None, None], 5) is None


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


class TestTruncateText:
    def test_short_text_unchanged(self) -> None:
        assert truncate_text("hello", 100) == "hello"

    def test_truncates_with_ellipsis(self) -> None:
        result = truncate_text("hello world", 6)
        assert result is not None
        assert len(result) <= 6
        assert result.endswith("\u2026")

    def test_none_returns_none(self) -> None:
        assert truncate_text(None, 100) is None

    def test_empty_string_returns_none(self) -> None:
        assert truncate_text("", 100) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert truncate_text("   ", 100) is None

    def test_non_string_returns_none(self) -> None:
        assert truncate_text(42, 100) is None  # type: ignore[arg-type]

    def test_exact_length_not_truncated(self) -> None:
        assert truncate_text("abcde", 5) == "abcde"


# ---------------------------------------------------------------------------
# strip_tags
# ---------------------------------------------------------------------------


class TestStripTags:
    def test_removes_html_tags(self) -> None:
        assert strip_tags("<p>Hello <b>world</b></p>") == "Hello world"

    def test_unescapes_html_entities(self) -> None:
        assert strip_tags("&amp; &lt;tag&gt;") == "& <tag>"

    def test_normalizes_whitespace(self) -> None:
        assert strip_tags("hello   world") == "hello world"

    def test_empty_string(self) -> None:
        assert strip_tags("") == ""


# ---------------------------------------------------------------------------
# decode_ddg_redirect
# ---------------------------------------------------------------------------


class TestDecodeDdgRedirect:
    def test_decodes_redirect_url(self) -> None:
        href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"
        assert decode_ddg_redirect(href) == "https://example.com/page"

    def test_passthrough_non_ddg(self) -> None:
        href = "https://example.com/direct"
        assert decode_ddg_redirect(href) == "https://example.com/direct"

    def test_empty_string(self) -> None:
        assert decode_ddg_redirect("") == ""

    def test_none_input(self) -> None:
        assert decode_ddg_redirect(None) == ""  # type: ignore[arg-type]

    def test_protocol_relative_non_ddg(self) -> None:
        href = "//example.com/page"
        assert decode_ddg_redirect(href) == "https://example.com/page"

    def test_ddg_without_uddg_param(self) -> None:
        href = "https://duckduckgo.com/l/?other=value"
        assert decode_ddg_redirect(href) == "https://duckduckgo.com/l/?other=value"


# ---------------------------------------------------------------------------
# candidate_queries
# ---------------------------------------------------------------------------


class TestCandidateQueries:
    def test_empty_query(self) -> None:
        assert candidate_queries("") == []
        assert candidate_queries("  ") == []

    def test_single_word(self) -> None:
        result = candidate_queries("malaria")
        assert result == ["malaria"]

    def test_two_words(self) -> None:
        result = candidate_queries("hello world")
        assert "hello world" in result

    def test_long_query_drops_last_word(self) -> None:
        result = candidate_queries("A B C")
        assert "A B C" in result
        assert "A B" in result

    def test_filters_low_value_tokens(self) -> None:
        result = candidate_queries("smith biography parasitologist details")
        # The full query is first
        assert result[0] == "smith biography parasitologist details"
        # Drops last word
        assert "smith biography parasitologist" in result
        # Filtered: removes "biography" and "parasitologist" (low-value),
        # leaving "smith details" (>= 2 words)
        assert "smith details" in result

    def test_no_duplicates(self) -> None:
        result = candidate_queries("hello world")
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# looks_blocked
# ---------------------------------------------------------------------------


class TestLooksBlocked:
    def test_status_202_is_blocked(self) -> None:
        assert looks_blocked(202, "<html></html>") is True

    def test_challenge_without_results_is_blocked(self) -> None:
        assert looks_blocked(200, "<html>challenge page</html>") is True

    def test_challenge_with_results_is_not_blocked(self) -> None:
        assert looks_blocked(200, "<html>challenge result__a</html>") is False

    def test_unusual_traffic_is_blocked(self) -> None:
        assert looks_blocked(200, "<html>unusual traffic detected</html>") is True

    def test_normal_page_not_blocked(self) -> None:
        assert looks_blocked(200, "<html>normal page result__a</html>") is False

    def test_empty_body_not_blocked(self) -> None:
        assert looks_blocked(200, "") is False


# ---------------------------------------------------------------------------
# norm_for_match / fallback_ratio / fuzzy_score
# ---------------------------------------------------------------------------


class TestNormForMatch:
    def test_normalizes_text(self) -> None:
        assert norm_for_match("  Hello  World  ") == "hello world"

    def test_non_string_returns_empty(self) -> None:
        assert norm_for_match(None) == ""
        assert norm_for_match(42) == ""  # type: ignore[arg-type]


class TestFallbackRatio:
    def test_identical_strings(self) -> None:
        assert fallback_ratio("abc", "abc") == 100.0

    def test_empty_strings(self) -> None:
        assert fallback_ratio("", "abc") == 0.0
        assert fallback_ratio("abc", "") == 0.0

    def test_similar_strings(self) -> None:
        score = fallback_ratio("hello", "hallo")
        assert 0 < score < 100


class TestFuzzyScore:
    def test_empty_input(self) -> None:
        assert fuzzy_score("", "text") == 0.0
        assert fuzzy_score("query", "") == 0.0

    def test_identical_strings_high_score(self) -> None:
        score = fuzzy_score("malaria", "malaria")
        assert score > 90.0


# ---------------------------------------------------------------------------
# rerank_score
# ---------------------------------------------------------------------------


class TestRerankScore:
    def test_returns_tuple_of_score_and_parts(self) -> None:
        item = {"title": "malaria", "abstract": "about malaria", "journal": "Nature"}
        score, parts = rerank_score("malaria", item)
        assert isinstance(score, float)
        assert "title" in parts
        assert "abstract" in parts
        assert "journal" in parts

    def test_empty_item(self) -> None:
        score, _parts = rerank_score("malaria", {})
        assert score == 0.0

    def test_weights_title_higher(self) -> None:
        item_title = {"title": "malaria", "abstract": "unrelated"}
        item_abstract = {"title": "unrelated", "abstract": "malaria"}
        score_title, _ = rerank_score("malaria", item_title)
        score_abstract, _ = rerank_score("malaria", item_abstract)
        assert score_title > score_abstract


# ---------------------------------------------------------------------------
# passes_filters
# ---------------------------------------------------------------------------


_DEFAULT_ITEM = LiteratureItemContext(
    title="Test",
    authors=None,
    year=2020,
    doi="10.1234/x",
    pmid="123",
    journal="Nature",
)


class TestPassesFilters:
    def test_passes_with_no_filters(self) -> None:
        assert passes_filters(_DEFAULT_ITEM, LiteratureFilters()) is True

    def test_year_from_filter(self) -> None:
        assert passes_filters(_DEFAULT_ITEM, LiteratureFilters(year_from=2019)) is True
        assert passes_filters(_DEFAULT_ITEM, LiteratureFilters(year_from=2021)) is False

    def test_year_to_filter(self) -> None:
        assert passes_filters(_DEFAULT_ITEM, LiteratureFilters(year_to=2021)) is True
        assert passes_filters(_DEFAULT_ITEM, LiteratureFilters(year_to=2019)) is False

    def test_year_none_fails_year_filter(self) -> None:
        item = LiteratureItemContext(
            title="Test",
            authors=None,
            year=None,
            doi="10.1234/x",
            pmid="123",
            journal="Nature",
        )
        assert passes_filters(item, LiteratureFilters(year_from=2019)) is False

    def test_require_doi(self) -> None:
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(require_doi=True)) is True
        )
        item_no_doi = LiteratureItemContext(
            title="Test",
            authors=None,
            year=2020,
            doi=None,
            pmid="123",
            journal="Nature",
        )
        assert passes_filters(item_no_doi, LiteratureFilters(require_doi=True)) is False
        item_empty_doi = LiteratureItemContext(
            title="Test", authors=None, year=2020, doi="", pmid="123", journal="Nature"
        )
        assert (
            passes_filters(item_empty_doi, LiteratureFilters(require_doi=True)) is False
        )

    def test_doi_equals(self) -> None:
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(doi_equals="10.1234/x"))
            is True
        )
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(doi_equals="10.9999/y"))
            is False
        )

    def test_pmid_equals(self) -> None:
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(pmid_equals="123")) is True
        )
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(pmid_equals="999")) is False
        )

    def test_title_includes(self) -> None:
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(title_includes="test"))
            is True
        )
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(title_includes="absent"))
            is False
        )

    def test_journal_includes(self) -> None:
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(journal_includes="nature"))
            is True
        )
        assert (
            passes_filters(_DEFAULT_ITEM, LiteratureFilters(journal_includes="science"))
            is False
        )

    def test_author_includes(self) -> None:
        item_with_authors = LiteratureItemContext(
            title="Test",
            authors=["Alice Smith", "Bob"],
            year=2020,
            doi="10.1234/x",
            pmid="123",
            journal="Nature",
        )
        assert (
            passes_filters(
                item_with_authors,
                LiteratureFilters(author_includes="alice"),
            )
            is True
        )
        item_alice = LiteratureItemContext(
            title="Test",
            authors=["Alice"],
            year=2020,
            doi="10.1234/x",
            pmid="123",
            journal="Nature",
        )
        assert (
            passes_filters(
                item_alice,
                LiteratureFilters(author_includes="bob"),
            )
            is False
        )

    def test_author_includes_with_none_authors(self) -> None:
        item_no_authors = LiteratureItemContext(
            title="Test",
            authors=None,
            year=2020,
            doi="10.1234/x",
            pmid="123",
            journal="Nature",
        )
        assert (
            passes_filters(
                item_no_authors,
                LiteratureFilters(author_includes="alice"),
            )
            is False
        )


# ---------------------------------------------------------------------------
# dedupe_key
# ---------------------------------------------------------------------------


class TestDedupeKey:
    def test_prefers_pmid(self) -> None:
        item = {
            "pmid": "123",
            "doi": "10/x",
            "url": "http://x",
            "title": "T",
            "year": 2020,
        }
        assert dedupe_key(item) == "pmid:123"

    def test_falls_back_to_doi(self) -> None:
        item = {"doi": "10/x", "url": "http://x", "title": "T", "year": 2020}
        assert dedupe_key(item) == "doi:10/x"

    def test_falls_back_to_url(self) -> None:
        item = {"url": "http://x", "title": "T", "year": 2020}
        assert dedupe_key(item) == "url:http://x"

    def test_falls_back_to_title_year(self) -> None:
        item = {"title": "Some Title", "year": 2020}
        assert "title:" in dedupe_key(item)
        assert "year:2020" in dedupe_key(item)


# ---------------------------------------------------------------------------
# fetch_page_summary (async, uses httpx)
# ---------------------------------------------------------------------------


class TestFetchPageSummary:
    async def test_returns_none_for_non_string(self) -> None:
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(client, None, max_chars=500)
        assert result is None

    async def test_returns_none_for_pdf(self) -> None:
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "http://example.com/file.pdf", max_chars=500
            )
        assert result is None

    async def test_returns_none_for_scholar(self) -> None:
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://scholar.google.com/page", max_chars=500
            )
        assert result is None

    @respx.mock
    async def test_extracts_meta_description(self) -> None:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(
                200,
                text='<html><head><meta name="description" content="This is the description"></head><body></body></html>',
            )
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result == "This is the description"

    @respx.mock
    async def test_extracts_og_description(self) -> None:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(
                200,
                text='<html><head><meta property="og:description" content="OG description here"></head><body></body></html>',
            )
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result == "OG description here"

    @respx.mock
    async def test_falls_back_to_longest_paragraph(self) -> None:
        html = """<html><body>
        <p>Short para</p>
        <p>This is a much longer paragraph that describes the content in detail and should be selected because it is the longest one available in the page.</p>
        </body></html>"""
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(200, text=html)
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result is not None
        assert "much longer paragraph" in result

    @respx.mock
    async def test_skips_nav_paragraphs(self) -> None:
        html = """<html><body>
        <p>Toggle navigation main menu items</p>
        <p>This is real content paragraph that has useful information and exceeds the minimum character threshold.</p>
        </body></html>"""
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(200, text=html)
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result is not None
        assert "toggle navigation" not in result.lower()

    @respx.mock
    async def test_returns_none_on_http_error(self) -> None:
        respx.get("https://example.com/page").mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result is None

    @respx.mock
    async def test_returns_none_when_no_content(self) -> None:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_page_summary(
                client, "https://example.com/page", max_chars=500
            )
        assert result is None
