"""Citation domain types and utilities."""

from __future__ import annotations

import re as _re
from dataclasses import dataclass
from datetime import UTC, datetime
from string import ascii_lowercase
from typing import Literal, cast
from uuid import uuid4

from veupath_chatbot.platform.types import JSONObject, JSONValue

CitationSource = Literal[
    "web",
    "europepmc",
    "crossref",
    "openalex",
    "semanticscholar",
    "pubmed",
    "arxiv",
    "biorxiv",
    "medrxiv",
]
LiteratureSource = Literal[
    "europepmc",
    "crossref",
    "openalex",
    "semanticscholar",
    "pubmed",
    "arxiv",
    "biorxiv",
    "medrxiv",
    "all",
]
LiteratureSort = Literal["relevance", "newest"]


@dataclass(frozen=True)
class Citation:
    id: str
    source: CitationSource
    title: str
    url: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    snippet: str | None = None
    accessed_at: str | None = None

    def to_dict(self) -> JSONObject:
        tag = _suggest_citation_tag(
            source=self.source,
            title=self.title,
            authors=self.authors,
            year=self.year,
            doi=self.doi,
            pmid=self.pmid,
            url=self.url,
        )
        return {
            "id": self.id,
            "source": self.source,
            "tag": tag,
            "title": self.title,
            "url": self.url,
            "authors": cast(JSONValue, self.authors),
            "year": self.year,
            "doi": self.doi,
            "pmid": self.pmid,
            "snippet": self.snippet,
            "accessedAt": self.accessed_at,
        }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_citation_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _slug_token(value: str | None, *, max_len: int = 32) -> str:
    if not isinstance(value, str):
        return ""
    t = value.strip().lower()
    if not t:
        return ""
    t = _re.sub(r"[^a-z0-9]+", "", t)
    return t[:max_len]


def _suggest_citation_tag(
    *,
    source: CitationSource,
    title: str,
    authors: list[str] | None,
    year: int | None,
    doi: str | None,
    pmid: str | None,
    url: str | None,
) -> str:
    first_author: str | None = None
    if authors and len(authors) > 0:
        first_author = authors[0] if isinstance(authors[0], str) else None
    first_last = (
        _slug_token(str(first_author).split(",")[0].split()[0]) if first_author else ""
    )
    if first_last and year:
        return f"{first_last}{year}"
    if first_last:
        return first_last

    first_word = (
        _slug_token(title.split()[0])
        if isinstance(title, str) and title.split()
        else ""
    )
    if first_word and year:
        return f"{first_word}{year}"

    title_slug = _slug_token(title, max_len=20)
    if title_slug:
        return title_slug

    stable = _slug_token(doi or pmid or url, max_len=20)
    return stable or str(source)


def ensure_unique_citation_tags(citations: list[JSONObject]) -> None:
    """Ensure all citation tags are unique by appending suffixes if needed.

    :param citations: Citation objects.

    """
    used: dict[str, int] = {}
    for c in citations:
        if not isinstance(c, dict):
            continue
        base = _slug_token(str(c.get("tag") or ""), max_len=40) or "ref"
        n = used.get(base, 0)
        if n == 0:
            tag = base
        else:
            if n <= len(ascii_lowercase):
                tag = f"{base}{ascii_lowercase[n - 1]}"
            else:
                tag = f"{base}_{n + 1}"
        used[base] = n + 1
        c["tag"] = tag


# Private utilities exported for use by services module
# These are implementation details but need to be accessible
