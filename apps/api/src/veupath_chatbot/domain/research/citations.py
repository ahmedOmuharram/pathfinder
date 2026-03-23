"""Citation domain types and utilities."""

import re
from datetime import UTC, datetime
from string import ascii_lowercase
from typing import Literal
from uuid import uuid4

from pydantic import ConfigDict, computed_field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject

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


class LiteratureFilters(CamelModel):
    """Post-retrieval filters for literature results."""

    year_from: int | None = None
    year_to: int | None = None
    author_includes: str | None = None
    title_includes: str | None = None
    journal_includes: str | None = None
    doi_equals: str | None = None
    pmid_equals: str | None = None
    require_doi: bool = False


class LiteratureOutputOptions(CamelModel):
    """Output formatting options for literature results."""

    include_abstract: bool = False
    abstract_max_chars: int = 2000
    max_authors: int = 2


def _slug_token(value: str | None, *, max_len: int = 32) -> str:
    if not isinstance(value, str):
        return ""
    t = value.strip().lower()
    if not t:
        return ""
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t[:max_len]


def _suggest_tag(citation: "Citation") -> str:
    """Derive a short slug tag from a Citation's metadata."""
    title = citation.title
    authors = citation.authors
    year = citation.year

    first_author: str | None = None
    if authors and len(authors) > 0:
        first_author = authors[0] if isinstance(authors[0], str) else None
    parts = str(first_author).split(",")[0].split() if first_author else []
    first_last = _slug_token(parts[0]) if parts else ""

    if first_last:
        return f"{first_last}{year}" if year else first_last

    first_word = (
        _slug_token(title.split(maxsplit=1)[0])
        if isinstance(title, str) and title.split()
        else ""
    )
    tag_from_word = f"{first_word}{year}" if (first_word and year) else first_word
    if tag_from_word:
        return tag_from_word

    stable = _slug_token(title, max_len=20) or _slug_token(
        citation.doi or citation.pmid or citation.url, max_len=20
    )
    return stable or str(citation.source)


class Citation(CamelModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: Literal[
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
    title: str
    url: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    snippet: str | None = None
    accessed_at: str | None = None

    @computed_field
    @property
    def tag(self) -> str:
        """Short tag for inline references (e.g. ``[pubmed-kinase]``)."""
        return _suggest_tag(self)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_citation_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


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
        elif n <= len(ascii_lowercase):
            tag = f"{base}{ascii_lowercase[n - 1]}"
        else:
            tag = f"{base}_{n + 1}"
        used[base] = n + 1
        c["tag"] = tag


# Private utilities exported for use by services module
# These are implementation details but need to be accessible
