"""What the research tools take, and what they hand back to the model."""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import BaseModel, Field


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


class WebResultOut(CamelModel):
    """One web result, as the model reads it."""

    title: str
    url: str | None = None
    snippet: str = ""


class WebSearchOut(CamelModel):
    """Ranked web results. The leading ones carry the page text."""

    query: str
    results: list[WebResultOut] = Field(default_factory=list)
    guidance: str = ""
    error: str | None = None


class PaperOut(CamelModel):
    """One paper, as the model reads it."""

    title: str
    year: int | None = None
    journal: str | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    abstract: str = ""


class LiteratureSearchOut(CamelModel):
    """Ranked papers. The leading ones carry the abstract."""

    query: str
    results: list[PaperOut] = Field(default_factory=list)
    guidance: str = ""
