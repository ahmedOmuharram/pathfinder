"""Utility functions for research services."""

import html
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from rapidfuzz import fuzz

from veupath_chatbot.domain.research.citations import LiteratureFilters
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)

_MIN_QUERY_WORD_COUNT = 2


@dataclass
class LiteratureItemContext:
    """Fields extracted from a literature result for filter evaluation."""

    title: str
    authors: list[str] | None
    year: int | None
    doi: str | None
    pmid: str | None
    journal: str | None


_MIN_FILTERED_WORD_COUNT = 2
_MIN_BIGRAM_WORD_COUNT = 2
_HTTP_ACCEPTED = 202
# Filter out short <p> tags (nav items, footers, etc.) when extracting
# page summaries — only keep paragraphs likely to contain real content.
_MIN_PARAGRAPH_LENGTH = 60

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def norm_text(value: str | None) -> str:
    """Normalize text for comparison.

    :param value: Text to normalize.
    :returns: Normalized string.
    """
    return (value or "").strip().lower()


def list_str(value: JSONValue) -> list[str]:
    """Convert a JSON value to a list of strings.

    :param value: Value to process.

    """
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def limit_authors(authors: list[str] | None, max_authors: int) -> list[str] | None:
    """Limit the number of authors, appending 'et al.' if truncated.

    :param authors: Author list.
    :param max_authors: Maximum number of authors (-1 for no limit).
    :returns: Truncated list or None.
    """
    cleaned = (
        [str(a) for a in authors if a is not None and str(a).strip()]
        if isinstance(authors, list) and authors
        else []
    )
    if not cleaned:
        return None
    if max_authors == -1 or len(cleaned) <= max_authors:
        return cleaned
    n = int(max_authors)
    return ["et al."] if n <= 0 else [*cleaned[:n], "et al."]


def truncate_text(text: str | None, max_chars: int) -> str | None:
    """Truncate text to max_chars, appending ellipsis if truncated.

    :param text: Text to truncate.
    :param max_chars: Maximum character count.
    :returns: Truncated string or None.
    """
    if not isinstance(text, str):
        return None
    t = text.strip()
    if not t:
        return None
    return t if len(t) <= max_chars else t[: max_chars - 1].rstrip() + "…"


def strip_tags(text: str) -> str:
    """Remove HTML tags and normalize whitespace.

    :param text: HTML string.
    :returns: Plain text.
    """
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def decode_ddg_redirect(href: str) -> str:
    """Decode DuckDuckGo redirect URLs.

    :param href: Redirect URL.
    :returns: Decoded URL.
    """
    h = (href or "").strip()
    if not h:
        return h
    if h.startswith("//"):
        h = "https:" + h
    result = h
    try:
        u = urlparse(h)
        if "duckduckgo.com" in (u.netloc or "") and u.path.startswith("/l/"):
            qs = parse_qs(u.query or "")
            uddg = qs.get("uddg", [None])[0]
            if isinstance(uddg, str) and uddg:
                result = unquote(uddg)
    except (ValueError, TypeError, KeyError) as exc:
        logger.debug("Failed to decode DDG redirect URL", error=str(exc))
    return result


_LOW_VALUE_QUERY_TOKENS = {
    "biography",
    "bio",
    "wikipedia",
    "parasitologist",
    "profile",
    "about",
    "department",
    "university",
}


def candidate_queries(q: str) -> list[str]:
    """Generate candidate query variations for fallback searches.

    :param q: Search query.
    :returns: Candidate query variations.
    """
    raw = (q or "").strip()
    if not raw:
        return []
    words = [w for w in raw.split() if w.strip()]
    cands: list[str] = []

    def _add(x: str) -> None:
        x = (x or "").strip()
        if x and x not in cands:
            cands.append(x)

    _add(raw)
    if len(words) > _MIN_QUERY_WORD_COUNT:
        _add(" ".join(words[:-1]))
    filtered = [w for w in words if w.lower() not in _LOW_VALUE_QUERY_TOKENS]
    if len(filtered) >= _MIN_FILTERED_WORD_COUNT:
        _add(" ".join(filtered))
    if len(words) >= _MIN_BIGRAM_WORD_COUNT:
        _add(" ".join(words[:2]))
    return cands


def looks_blocked(status_code: int, html: str) -> bool:
    """Check if a response looks like it was blocked by rate limiting.

    :param status_code: HTTP status code.
    :param html: Response HTML body.
    :returns: True if response looks blocked.
    """
    if status_code == _HTTP_ACCEPTED:
        return True
    h = (html or "").lower()
    if "challenge" in h and "result__a" not in h:
        return True
    return bool("unusual traffic" in h and "result__a" not in h)


def norm_for_match(text: str | None) -> str:
    """Normalize text for fuzzy matching.

    :param text: Text to normalize.
    :returns: Normalized string for matching.
    """
    if not isinstance(text, str):
        return ""
    t = text.lower()
    return re.sub(r"\s+", " ", t).strip()


def fallback_ratio(a: str, b: str) -> float:
    """Fallback similarity ratio using SequenceMatcher.

    :param a: First string.
    :param b: Second string.
    :returns: Similarity ratio (0-100).
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def fuzzy_score(query: str, text: str) -> float:
    """Calculate fuzzy similarity score between query and text.

    :param query: Search query.
    :param text: Text to score.
    :returns: Fuzzy similarity score.
    """
    q = norm_for_match(query)
    t = norm_for_match(text)
    if not q or not t:
        return 0.0
    try:
        return float(fuzz.token_set_ratio(q, t))
    except (ValueError, TypeError) as exc:
        logger.debug("rapidfuzz unavailable, using fallback ratio", error=str(exc))
        return fallback_ratio(q, t)


def rerank_score(query: str, item: JSONObject) -> tuple[float, dict[str, float]]:
    """Calculate reranking score for a literature search result.

    :param query: Search query.
    :param item: Literature result item.
    :returns: Tuple of (score, score breakdown).
    """
    title = str(item.get("title") or "")
    abstract = str(item.get("abstract") or item.get("snippet") or "")
    journal = str(item.get("journalTitle") or item.get("journal") or "")
    title_s = fuzzy_score(query, title)
    abs_s = fuzzy_score(query, abstract)
    journal_s = fuzzy_score(query, journal) if journal else 0.0
    score = 0.70 * title_s + 0.28 * abs_s + 0.02 * journal_s
    return score, {"title": title_s, "abstract": abs_s, "journal": journal_s}


def passes_filters(item: LiteratureItemContext, filters: LiteratureFilters) -> bool:
    """Check if a literature result passes all filters.

    :param item: Item fields to check (title, authors, year, doi, pmid, journal).
    :param filters: Filter criteria to apply.
    :returns: True if result passes all filters.
    """
    year_ok = (
        filters.year_from is None
        or (item.year is not None and item.year >= filters.year_from)
    ) and (
        filters.year_to is None
        or (item.year is not None and item.year <= filters.year_to)
    )
    doi_ok = not filters.require_doi or (
        isinstance(item.doi, str) and bool(item.doi.strip())
    )
    exact_ok = (
        filters.doi_equals is None
        or norm_text(item.doi) == norm_text(filters.doi_equals)
    ) and (
        filters.pmid_equals is None
        or norm_text(item.pmid) == norm_text(filters.pmid_equals)
    )
    needle_author = (
        norm_text(filters.author_includes)
        if filters.author_includes is not None
        else None
    )
    haystack = " ".join(norm_text(a) for a in (item.authors or []))
    text_ok = (
        (
            filters.title_includes is None
            or norm_text(filters.title_includes) in norm_text(item.title)
        )
        and (
            filters.journal_includes is None
            or norm_text(filters.journal_includes) in norm_text(item.journal)
        )
        and (needle_author is None or needle_author in haystack)
    )
    return year_ok and doi_ok and exact_ok and text_ok


def dedupe_key(item: JSONObject) -> str:
    """Generate a deduplication key for a literature result.

    :param item: Item dict.

    """
    pmid = item.get("pmid")
    doi = item.get("doi")
    url = item.get("url")
    if isinstance(pmid, str) and pmid.strip():
        key: str = f"pmid:{pmid.strip().lower()}"
    elif isinstance(doi, str) and doi.strip():
        key = f"doi:{doi.strip().lower()}"
    elif isinstance(url, str) and url.strip():
        key = f"url:{url.strip().lower()}"
    else:
        key = f"title:{norm_text(str(item.get('title')))}|year:{item.get('year')}"
    return key


_HEAD_LIMIT = 32 * 1024  # 32 KB — more than enough to capture <head>

_META_PATTERNS = [
    re.compile(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
]


def _extract_meta_description(text: str) -> str | None:
    """Try each meta-description pattern and return the first match."""
    for pat in _META_PATTERNS:
        m = pat.search(text)
        if m:
            return strip_tags(m.group(1)) or None
    return None


def _extract_best_paragraph(text: str) -> str | None:
    """Return the longest non-boilerplate ``<p>`` content."""
    paras = re.findall(r"<p[^>]*>(.*?)</p>", text, flags=re.IGNORECASE | re.DOTALL)
    best: str | None = None
    for p in paras:
        txt = strip_tags(p)
        low = txt.lower()
        if len(txt) < _MIN_PARAGRAPH_LENGTH:
            continue
        if "toggle navigation" in low or "main navigation" in low:
            continue
        if best is None or len(txt) > len(best):
            best = txt
    return best


async def fetch_page_summary(
    client: httpx.AsyncClient, url: JSONValue, *, max_chars: int
) -> str | None:
    """Fetch and extract a text summary from a web page.

    Streams the response and stops reading as soon as ``</head>`` is found or
    32 KB have been consumed.  Meta description tags are checked first; if none
    are present the longest ``<p>`` in the buffered content is used as a
    fallback.  Returns ``None`` for PDFs, Google Scholar links, or on error.
    """
    u = url.strip() if isinstance(url, str) else ""
    is_skippable = not u or u.lower().endswith(".pdf") or "scholar.google." in u
    if is_skippable:
        return None

    buf = ""
    head_closed = False
    fetch_error = False
    try:
        async with client.stream(
            "GET",
            u,
            follow_redirects=True,
            headers={"Referer": "https://duckduckgo.com/"},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_text():
                buf += chunk
                if "</head>" in buf.lower():
                    head_closed = True
                    break
                if len(buf) >= _HEAD_LIMIT:
                    break
    except httpx.HTTPError as exc:
        logger.debug("Failed to fetch page for summary extraction", error=str(exc))
        fetch_error = True

    if fetch_error:
        return None
    # --- Try meta descriptions (always in <head>) ---
    search_region = buf[: buf.lower().find("</head>") + 7] if head_closed else buf
    desc = _extract_meta_description(search_region)
    text = desc or _extract_best_paragraph(buf)
    return truncate_text(text, max_chars)
