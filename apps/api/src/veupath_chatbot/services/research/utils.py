"""Utility functions for research services."""

from __future__ import annotations

import html as _html
import re as _re
from difflib import SequenceMatcher
from urllib.parse import parse_qs, unquote, urlparse

from veupath_chatbot.platform.types import JSONObject, JSONValue


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
    if not isinstance(authors, list) or not authors:
        return None
    cleaned = [str(a) for a in authors if a is not None and str(a).strip()]
    if not cleaned:
        return None
    if max_authors == -1:
        return cleaned
    n = int(max_authors)
    if n <= 0:
        return ["et al."]
    if len(cleaned) <= n:
        return cleaned
    return cleaned[:n] + ["et al."]


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
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def strip_tags(text: str) -> str:
    """Remove HTML tags and normalize whitespace.

    :param text: HTML string.
    :returns: Plain text.
    """
    cleaned = _re.sub(r"<[^>]+>", " ", text)
    cleaned = _html.unescape(cleaned)
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


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
    try:
        u = urlparse(h)
        if "duckduckgo.com" in (u.netloc or "") and u.path.startswith("/l/"):
            qs = parse_qs(u.query or "")
            uddg = qs.get("uddg", [None])[0]
            if isinstance(uddg, str) and uddg:
                return unquote(uddg)
    except Exception:
        return h
    return h


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
    if len(words) > 2:
        _add(" ".join(words[:-1]))
    filtered = [w for w in words if w.lower() not in _LOW_VALUE_QUERY_TOKENS]
    if len(filtered) >= 2:
        _add(" ".join(filtered))
    if len(words) >= 2:
        _add(" ".join(words[:2]))
    return cands


def looks_blocked(status_code: int, html: str) -> bool:
    """Check if a response looks like it was blocked by rate limiting.

    :param status_code: HTTP status code.
    :param html: Response HTML body.
    :returns: True if response looks blocked.
    """
    if status_code == 202:
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
    t = _re.sub(r"\s+", " ", t).strip()
    return t


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
        from rapidfuzz import fuzz

        return float(fuzz.token_set_ratio(q, t))
    except Exception:
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


def passes_filters(
    *,
    title: str,
    authors: list[str] | None,
    year: int | None,
    doi: str | None,
    pmid: str | None,
    journal: str | None,
    year_from: int | None,
    year_to: int | None,
    author_includes: str | None,
    title_includes: str | None,
    journal_includes: str | None,
    doi_equals: str | None,
    pmid_equals: str | None,
    require_doi: bool,
) -> bool:
    """Check if a literature result passes all filters.

    :param title: Result title.
    :param authors: Author list.
    :param year: Publication year.
    :param doi: DOI.
    :param pmid: PubMed ID.
    :param journal: Journal name.
    :param year_from: Minimum year filter.
    :param year_to: Maximum year filter.
    :param author_includes: Author substring filter.
    :param title_includes: Title substring filter.
    :param journal_includes: Journal substring filter.
    :param doi_equals: Exact DOI filter.
    :param pmid_equals: Exact PMID filter.
    :param require_doi: Whether DOI is required.
    :returns: True if result passes all filters.
    """
    if year_from is not None and (year is None or year < year_from):
        return False
    if year_to is not None and (year is None or year > year_to):
        return False

    if require_doi and not (isinstance(doi, str) and doi.strip()):
        return False

    if doi_equals is not None and norm_text(doi) != norm_text(doi_equals):
        return False
    if pmid_equals is not None and norm_text(pmid) != norm_text(pmid_equals):
        return False

    if title_includes is not None and norm_text(title_includes) not in norm_text(title):
        return False
    if journal_includes is not None and norm_text(journal_includes) not in norm_text(
        journal
    ):
        return False
    if author_includes is not None:
        needle = norm_text(author_includes)
        haystack = " ".join(norm_text(a) for a in (authors or []))
        if needle not in haystack:
            return False

    return True


def dedupe_key(item: JSONObject) -> str:
    """Generate a deduplication key for a literature result.

    :param item: Item dict.

    """
    pmid = item.get("pmid")
    doi = item.get("doi")
    url = item.get("url")
    title = item.get("title")
    year = item.get("year")
    if isinstance(pmid, str) and pmid.strip():
        return f"pmid:{pmid.strip().lower()}"
    if isinstance(doi, str) and doi.strip():
        return f"doi:{doi.strip().lower()}"
    if isinstance(url, str) and url.strip():
        return f"url:{url.strip().lower()}"
    return f"title:{norm_text(str(title))}|year:{year}"
