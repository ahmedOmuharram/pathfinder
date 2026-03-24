"""Parsed paper domain models and per-API raw paper models.

These models replace manual isinstance/dict.get() chains in literature
search clients by providing typed Pydantic models that normalize raw API
responses into a shared ``ParsedPaper`` representation.

Each API's nested structures (authors, journals, external IDs) are modeled
as typed Pydantic sub-models with ``extra="ignore"``, so ``model_validate``
handles all type coercion and unknown-field filtering.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veupath_chatbot.platform.pydantic_base import CamelModel


class ParsedPaper(CamelModel):
    """Normalized paper representation shared across all literature clients.

    All fields have safe defaults so partial API responses are handled
    gracefully.  ``extra="ignore"`` allows forward-compatible parsing.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal_title: str | None = None
    abstract: str | None = None
    snippet: str | None = None


# ── Semantic Scholar ────────────────────────────────────────────────────


class _S2Author(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""


class _S2Journal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""


class _S2ExternalIds(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doi: str | None = Field(None, alias="DOI")
    pub_med: str | None = Field(None, alias="PubMed")


class SemanticScholarRawPaper(BaseModel):
    """Raw paper from the Semantic Scholar API.

    Nested ``externalIds``, ``journal``, and ``authors`` are parsed via
    typed sub-models — no isinstance chains needed.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = ""
    year: int | None = None
    url: str | None = None
    abstract: str | None = None
    authors: list[_S2Author] = Field(default_factory=list)
    journal: _S2Journal | None = None
    external_ids: _S2ExternalIds | None = Field(None, alias="externalIds")

    def to_parsed_paper(self) -> ParsedPaper:
        """Convert to the shared normalized ParsedPaper model."""
        title = (self.title or "").strip()
        doi = self.external_ids.doi if self.external_ids else None
        pmid = self.external_ids.pub_med if self.external_ids else None
        journal_name = self.journal.name if self.journal and self.journal.name else None
        result_url = self.url or (f"https://doi.org/{doi}" if doi else None)
        author_names = [a.name for a in self.authors if a.name]
        return ParsedPaper(
            title=title,
            year=self.year,
            doi=doi,
            pmid=pmid,
            url=result_url,
            authors=author_names,
            journal_title=journal_name,
            abstract=self.abstract,
            snippet=self.abstract or journal_name,
        )


# ── OpenAlex ────────────────────────────────────────────────────────────


class _OAAuthorInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    display_name: str = ""


class _OAAuthorship(BaseModel):
    model_config = ConfigDict(extra="ignore")
    author: _OAAuthorInfo = Field(default_factory=_OAAuthorInfo)


class _OAHostVenue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    display_name: str = ""


class OpenAlexRawWork(BaseModel):
    """Raw work from the OpenAlex API.

    Handles DOI prefix stripping, inverted-index abstract reconstruction,
    nested authorships, and host_venue journal extraction via typed sub-models.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = ""
    publication_year: int | None = None
    doi: str | None = None
    id: str | None = None
    authorships: list[_OAAuthorship] = Field(default_factory=list)
    host_venue: _OAHostVenue | None = None
    abstract_inverted_index: dict[str, list[int]] | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_doi_prefix(cls, data: dict[str, object]) -> dict[str, object]:
        """Strip https://doi.org/ prefix from DOI if present."""
        doi_raw = data.get("doi")
        if isinstance(doi_raw, str) and doi_raw.startswith("https://doi.org/"):
            data["doi"] = doi_raw.removeprefix("https://doi.org/")
        return data

    def _reconstruct_abstract(self) -> str | None:
        """Reconstruct abstract text from OpenAlex inverted index."""
        inv = self.abstract_inverted_index
        if not inv:
            return None
        pairs: list[tuple[int, str]] = [
            (i, word) for word, idxs in inv.items() for i in idxs
        ]
        if not pairs:
            return None
        pairs.sort(key=lambda x: x[0])
        return " ".join(w for _, w in pairs)

    def to_parsed_paper(self) -> ParsedPaper:
        """Convert to the shared normalized ParsedPaper model."""
        title = (self.title or "").strip()
        result_url = f"https://doi.org/{self.doi}" if self.doi else self.id
        author_names = [
            a.author.display_name for a in self.authorships if a.author.display_name
        ]
        journal_name = (
            self.host_venue.display_name.strip()
            if self.host_venue and self.host_venue.display_name
            else None
        )
        abstract = self._reconstruct_abstract()
        return ParsedPaper(
            title=title,
            year=self.publication_year,
            doi=self.doi,
            url=result_url,
            authors=author_names,
            journal_title=journal_name,
            abstract=abstract,
            snippet=abstract or journal_name,
        )


# ── CrossRef ────────────────────────────────────────────────────────────


class _CRAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    given: str | None = None
    family: str | None = None

    @property
    def full_name(self) -> str | None:
        if self.family and self.given:
            return f"{self.given} {self.family}"
        return self.family


class _CRDateParts(BaseModel):
    """CrossRef date structure: ``{"date-parts": [[2021, 3, 15]]}``."""

    model_config = ConfigDict(extra="ignore")
    date_parts: list[list[int]] = Field(default_factory=list, alias="date-parts")

    @property
    def year(self) -> int | None:
        if self.date_parts and self.date_parts[0]:
            return self.date_parts[0][0]
        return None


class CrossRefRawWork(BaseModel):
    """Raw work from the CrossRef API.

    Nested structures (date-parts, title array, author array,
    container-title) are parsed via typed sub-models.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: list[str] = Field(default_factory=list)
    doi: str | None = Field(None, alias="DOI")
    url: str | None = Field(None, alias="URL")
    author: list[_CRAuthor] = Field(default_factory=list)
    container_title: list[str] = Field(default_factory=list, alias="container-title")
    published_print: _CRDateParts | None = Field(None, alias="published-print")
    published_online: _CRDateParts | None = Field(None, alias="published-online")

    def to_parsed_paper(self) -> ParsedPaper:
        """Convert to the shared normalized ParsedPaper model."""
        title = self.title[0].strip() if self.title else ""
        journal = self.container_title[0].strip() if self.container_title else None
        date_source = self.published_print or self.published_online
        year = date_source.year if date_source else None
        result_url = self.url or (f"https://doi.org/{self.doi}" if self.doi else None)
        author_names = [a.full_name for a in self.author if a.full_name]
        return ParsedPaper(
            title=title,
            year=year,
            doi=self.doi,
            url=result_url,
            authors=author_names,
            journal_title=journal,
            snippet=journal,
        )


# ── Europe PMC ──────────────────────────────────────────────────────────


class EuropePmcRawResult(BaseModel):
    """Raw result from the Europe PMC API.

    Field aliases map EuropePMC's camelCase keys to Python names.
    ``pubYear`` is coerced from str via Pydantic lax mode.
    ``authorString`` is split in a model_validator.
    """

    model_config = ConfigDict(
        extra="ignore", populate_by_name=True, coerce_numbers_to_str=False
    )

    title: str = ""
    pub_year: int | None = Field(None, alias="pubYear")
    doi: str | None = None
    pmid: str | None = None
    author_string: str | None = Field(None, alias="authorString")
    journal_title: str | None = Field(None, alias="journalTitle")
    abstract_text: str | None = Field(None, alias="abstractText")

    def to_parsed_paper(self) -> ParsedPaper:
        """Convert to the shared normalized ParsedPaper model."""
        title = (self.title or "").strip()
        link: str | None = None
        if self.doi:
            link = f"https://doi.org/{self.doi}"
        elif self.pmid:
            link = f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

        authors: list[str] = []
        if self.author_string:
            authors = [a.strip() for a in self.author_string.split(",") if a.strip()]

        jt = self.journal_title.strip() if self.journal_title else None

        return ParsedPaper(
            title=title,
            year=self.pub_year,
            doi=self.doi,
            pmid=self.pmid,
            url=link,
            authors=authors,
            journal_title=jt,
            abstract=self.abstract_text,
            snippet=jt,
        )
