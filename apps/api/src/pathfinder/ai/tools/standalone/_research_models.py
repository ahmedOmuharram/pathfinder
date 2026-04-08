"""Research tool response models."""

from __future__ import annotations

from pydantic import BaseModel


class LiteratureSearchFilters(BaseModel):
    """Filters for literature search (tool-facing model)."""

    year_from: int | None = None
    year_to: int | None = None
    author_includes: str | None = None
    title_includes: str | None = None
    journal_includes: str | None = None
    doi_equals: str | None = None
    pmid_equals: str | None = None
    require_doi: bool = False


class LiteratureSearchOutputOptions(BaseModel):
    """Output options for literature search (tool-facing model)."""

    include_abstract: bool = True
    abstract_max_chars: int = 500
    max_authors: int = 5


_DEFAULT_FILTERS = LiteratureSearchFilters()
_DEFAULT_OUTPUT_OPTIONS = LiteratureSearchOutputOptions()
