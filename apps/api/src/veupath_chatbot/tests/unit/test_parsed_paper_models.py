"""Tests for ParsedPaper domain model and per-API raw paper models.

Each raw model is tested with:
- Realistic API response data (validated against real API responses)
- Missing/null fields (model handles gracefully with defaults)
- Extra fields (ignored via extra="ignore")
- Edge cases specific to each API
"""

import pytest
from pydantic import ValidationError

from veupath_chatbot.domain.research.papers import (
    CrossRefRawWork,
    EuropePmcRawResult,
    OpenAlexRawWork,
    ParsedPaper,
    SemanticScholarRawPaper,
)

# ===========================================================================
# ParsedPaper — shared normalized model
# ===========================================================================


class TestParsedPaper:
    def test_defaults_all_optional_fields(self) -> None:
        paper = ParsedPaper()
        assert paper.title == ""
        assert paper.year is None
        assert paper.doi is None
        assert paper.pmid is None
        assert paper.url is None
        assert paper.authors == []
        assert paper.journal_title is None
        assert paper.abstract is None
        assert paper.snippet is None

    def test_accepts_full_data(self) -> None:
        paper = ParsedPaper(
            title="Malaria Genomics",
            year=2023,
            doi="10.1234/test",
            pmid="12345",
            url="https://doi.org/10.1234/test",
            authors=["Smith J", "Doe A"],
            journal_title="Nature",
            abstract="A comprehensive study.",
            snippet="A comprehensive study.",
        )
        assert paper.title == "Malaria Genomics"
        assert paper.year == 2023
        assert paper.doi == "10.1234/test"
        assert paper.pmid == "12345"
        assert paper.authors == ["Smith J", "Doe A"]
        assert paper.journal_title == "Nature"

    def test_camel_case_serialization(self) -> None:
        paper = ParsedPaper(
            title="Test",
            journal_title="Science",
        )
        dumped = paper.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert dumped["journalTitle"] == "Science"
        assert "journal_title" not in dumped

    def test_extra_fields_ignored(self) -> None:
        paper = ParsedPaper.model_validate(
            {"title": "Test", "unknown_field": "should be ignored"}
        )
        assert paper.title == "Test"
        assert not hasattr(paper, "unknown_field")


# ===========================================================================
# SemanticScholarRawPaper
# ===========================================================================


class TestSemanticScholarRawPaper:
    def test_full_response(self) -> None:
        raw = {
            "title": "S2 Paper",
            "year": 2022,
            "url": "https://semanticscholar.org/paper/123",
            "authors": [{"name": "Eve"}, {"name": "Frank"}],
            "abstract": "This is the abstract.",
            "journal": {"name": "Science"},
            "externalIds": {"DOI": "10.5555/s2", "PubMed": "77777"},
        }
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.title == "S2 Paper"
        assert paper.year == 2022
        assert paper.url == "https://semanticscholar.org/paper/123"
        assert [a.name for a in paper.authors] == ["Eve", "Frank"]
        assert paper.abstract == "This is the abstract."
        assert paper.journal is not None
        assert paper.journal.name == "Science"
        assert paper.external_ids is not None
        assert paper.external_ids.doi == "10.5555/s2"
        assert paper.external_ids.pub_med == "77777"

    def test_missing_external_ids(self) -> None:
        raw = {"title": "No IDs", "year": 2023, "url": "https://s2.org/1"}
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.external_ids is None
        assert paper.url == "https://s2.org/1"

    def test_missing_journal(self) -> None:
        raw = {"title": "No Journal"}
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.journal is None

    def test_empty_authors(self) -> None:
        raw = {"title": "Solo Author", "authors": []}
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.authors == []

    def test_authors_with_missing_name(self) -> None:
        raw = {"title": "Test", "authors": [{"name": "Good"}, {"affiliations": []}]}
        paper = SemanticScholarRawPaper.model_validate(raw)
        # Second author has default empty name from _S2Author
        assert [a.name for a in paper.authors if a.name] == ["Good"]

    def test_extra_fields_ignored(self) -> None:
        raw = {"title": "Test", "citationCount": 42, "influentialCitationCount": 5}
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.title == "Test"

    def test_none_year(self) -> None:
        raw = {"title": "No Year", "year": None}
        paper = SemanticScholarRawPaper.model_validate(raw)
        assert paper.year is None

    def test_to_parsed_paper(self) -> None:
        raw = {
            "title": "  S2 Paper  ",
            "year": 2022,
            "url": "https://s2.org/123",
            "authors": [{"name": "Eve"}],
            "abstract": "Abstract text.",
            "journal": {"name": "Science"},
            "externalIds": {"DOI": "10.5555/s2", "PubMed": "77777"},
        }
        paper = SemanticScholarRawPaper.model_validate(raw).to_parsed_paper()
        assert isinstance(paper, ParsedPaper)
        assert paper.title == "S2 Paper"
        assert paper.year == 2022
        assert paper.doi == "10.5555/s2"
        assert paper.pmid == "77777"
        assert paper.authors == ["Eve"]
        assert paper.journal_title == "Science"
        assert paper.abstract == "Abstract text."
        assert paper.snippet == "Abstract text."
        # URL should prefer the direct URL
        assert paper.url == "https://s2.org/123"

    def test_to_parsed_paper_url_fallback_to_doi(self) -> None:
        raw = {"title": "DOI only", "externalIds": {"DOI": "10.1/x"}}
        paper = SemanticScholarRawPaper.model_validate(raw).to_parsed_paper()
        assert paper.url == "https://doi.org/10.1/x"

    def test_to_parsed_paper_snippet_fallback_to_journal(self) -> None:
        raw = {"title": "No Abstract", "journal": {"name": "Nature"}}
        paper = SemanticScholarRawPaper.model_validate(raw).to_parsed_paper()
        assert paper.snippet == "Nature"


# ===========================================================================
# OpenAlexRawWork
# ===========================================================================


class TestOpenAlexRawWork:
    def test_full_response(self) -> None:
        raw = {
            "title": "OpenAlex paper",
            "publication_year": 2021,
            "doi": "https://doi.org/10.1111/oa",
            "id": "https://openalex.org/W123",
            "host_venue": {"display_name": "Cell"},
            "authorships": [
                {"author": {"display_name": "Alice Smith"}},
                {"author": {"display_name": "Bob Jones"}},
            ],
            "abstract_inverted_index": {
                "We": [0],
                "study": [1],
                "malaria": [2],
            },
        }
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper.title == "OpenAlex paper"
        assert paper.publication_year == 2021
        assert paper.doi == "10.1111/oa"  # prefix stripped
        assert paper.id == "https://openalex.org/W123"
        assert paper.host_venue is not None
        assert paper.host_venue.display_name == "Cell"
        assert [a.author.display_name for a in paper.authorships] == [
            "Alice Smith",
            "Bob Jones",
        ]
        assert paper._reconstruct_abstract() == "We study malaria"

    def test_no_doi_uses_openalex_id(self) -> None:
        raw = {"title": "No DOI", "id": "https://openalex.org/W456"}
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper.doi is None
        assert paper.id == "https://openalex.org/W456"

    def test_abstract_inverted_index_reconstruction(self) -> None:
        raw = {
            "title": "Test",
            "abstract_inverted_index": {
                "hello": [0],
                "world": [1],
                "foo": [2],
            },
        }
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper._reconstruct_abstract() == "hello world foo"

    def test_no_abstract_inverted_index(self) -> None:
        raw = {"title": "No Abstract"}
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper._reconstruct_abstract() is None

    def test_year_as_string(self) -> None:
        raw = {"title": "Str Year", "publication_year": "2019"}
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper.publication_year == 2019

    def test_no_host_venue(self) -> None:
        raw = {"title": "No Venue"}
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper.host_venue is None

    def test_extra_fields_ignored(self) -> None:
        raw = {
            "title": "Test",
            "cited_by_count": 100,
            "is_oa": True,
        }
        paper = OpenAlexRawWork.model_validate(raw)
        assert paper.title == "Test"

    def test_to_parsed_paper(self) -> None:
        raw = {
            "title": "  OA Paper  ",
            "publication_year": 2021,
            "doi": "https://doi.org/10.1111/oa",
            "id": "https://openalex.org/W123",
            "host_venue": {"display_name": "Cell"},
            "authorships": [{"author": {"display_name": "Alice"}}],
            "abstract_inverted_index": {"We": [0], "study": [1]},
        }
        paper = OpenAlexRawWork.model_validate(raw).to_parsed_paper()
        assert isinstance(paper, ParsedPaper)
        assert paper.title == "OA Paper"
        assert paper.doi == "10.1111/oa"
        assert paper.url == "https://doi.org/10.1111/oa"
        assert paper.journal_title == "Cell"
        assert paper.abstract == "We study"

    def test_to_parsed_paper_url_fallback_to_openalex_id(self) -> None:
        raw = {"title": "No DOI", "id": "https://openalex.org/W456"}
        paper = OpenAlexRawWork.model_validate(raw).to_parsed_paper()
        assert paper.url == "https://openalex.org/W456"


# ===========================================================================
# CrossRefRawWork
# ===========================================================================


class TestCrossRefRawWork:
    def test_full_response(self) -> None:
        raw = {
            "title": ["Plasmodium falciparum proteome"],
            "DOI": "10.1234/test",
            "URL": "https://doi.org/10.1234/test",
            "published-print": {"date-parts": [[2020, 3, 15]]},
            "author": [
                {"given": "John", "family": "Smith"},
                {"given": "Jane", "family": "Doe"},
            ],
            "container-title": ["Nature"],
        }
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.title == ["Plasmodium falciparum proteome"]
        assert paper.doi == "10.1234/test"
        assert paper.url == "https://doi.org/10.1234/test"
        assert paper.published_print is not None
        assert paper.published_print.year == 2020
        assert [a.full_name for a in paper.author if a.full_name] == [
            "John Smith",
            "Jane Doe",
        ]
        assert paper.container_title == ["Nature"]

    def test_family_only_author(self) -> None:
        raw = {
            "title": ["Test"],
            "DOI": "10.1/x",
            "author": [{"family": "Solo"}],
        }
        paper = CrossRefRawWork.model_validate(raw)
        assert [a.full_name for a in paper.author if a.full_name] == ["Solo"]

    def test_no_date_parts(self) -> None:
        raw = {"title": ["No Date"], "DOI": "10.1/nd"}
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.published_print is None
        assert paper.published_online is None

    def test_published_online_fallback(self) -> None:
        raw = {
            "title": ["Online"],
            "published-online": {"date-parts": [[2019]]},
        }
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.published_online is not None
        assert paper.published_online.year == 2019

    def test_empty_title_list(self) -> None:
        raw = {"title": [], "DOI": "10.1/empty"}
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.title == []

    def test_no_container_title(self) -> None:
        raw = {"title": ["Test"]}
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.container_title == []

    def test_extra_fields_ignored(self) -> None:
        raw = {
            "title": ["Test"],
            "DOI": "10.1/x",
            "is-referenced-by-count": 42,
            "type": "journal-article",
        }
        paper = CrossRefRawWork.model_validate(raw)
        assert paper.title == ["Test"]

    def test_to_parsed_paper(self) -> None:
        raw = {
            "title": ["  CrossRef Paper  "],
            "DOI": "10.1234/test",
            "URL": "https://doi.org/10.1234/test",
            "published-print": {"date-parts": [[2020]]},
            "author": [{"given": "John", "family": "Smith"}],
            "container-title": ["Nature"],
        }
        paper = CrossRefRawWork.model_validate(raw).to_parsed_paper()
        assert isinstance(paper, ParsedPaper)
        assert paper.title == "CrossRef Paper"
        assert paper.doi == "10.1234/test"
        assert paper.year == 2020
        assert paper.authors == ["John Smith"]
        assert paper.journal_title == "Nature"
        assert paper.snippet == "Nature"

    def test_to_parsed_paper_url_fallback_to_doi(self) -> None:
        raw = {"title": ["T"], "DOI": "10.1/x"}
        paper = CrossRefRawWork.model_validate(raw).to_parsed_paper()
        assert paper.url == "https://doi.org/10.1/x"


# ===========================================================================
# EuropePmcRawResult
# ===========================================================================


class TestEuropePmcRawResult:
    def test_full_response(self) -> None:
        raw = {
            "title": "Gametocyte proteome analysis",
            "pubYear": "2018",
            "doi": "10.9999/epmc",
            "pmid": "55555",
            "authorString": "Smith J, Doe A",
            "journalTitle": "PLoS One",
            "abstractText": "We analyzed the proteome...",
        }
        paper = EuropePmcRawResult.model_validate(raw)
        assert paper.title == "Gametocyte proteome analysis"
        assert paper.pub_year == 2018
        assert paper.doi == "10.9999/epmc"
        assert paper.pmid == "55555"
        assert paper.author_string == "Smith J, Doe A"
        assert paper.journal_title == "PLoS One"
        assert paper.abstract_text == "We analyzed the proteome..."

    def test_year_as_int(self) -> None:
        raw = {"title": "T", "pubYear": 2020}
        paper = EuropePmcRawResult.model_validate(raw)
        assert paper.pub_year == 2020

    def test_year_as_non_digit_string_raises(self) -> None:
        raw = {"title": "T", "pubYear": "N/A"}
        with pytest.raises(ValidationError, match="int_parsing"):
            EuropePmcRawResult.model_validate(raw)

    def test_no_pub_year(self) -> None:
        raw = {"title": "T"}
        paper = EuropePmcRawResult.model_validate(raw)
        assert paper.pub_year is None

    def test_no_author_string(self) -> None:
        raw = {"title": "T"}
        paper = EuropePmcRawResult.model_validate(raw)
        assert paper.author_string is None

    def test_constructs_doi_url(self) -> None:
        raw = {"title": "T", "doi": "10.1/x"}
        paper = EuropePmcRawResult.model_validate(raw).to_parsed_paper()
        assert paper.url == "https://doi.org/10.1/x"

    def test_constructs_pubmed_url_when_no_doi(self) -> None:
        raw = {"title": "T", "pmid": "999"}
        paper = EuropePmcRawResult.model_validate(raw).to_parsed_paper()
        assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/999/"

    def test_extra_fields_ignored(self) -> None:
        raw = {
            "title": "T",
            "citedByCount": 10,
            "isOpenAccess": "Y",
        }
        paper = EuropePmcRawResult.model_validate(raw)
        assert paper.title == "T"

    def test_to_parsed_paper(self) -> None:
        raw = {
            "title": "  EPMC Paper  ",
            "pubYear": "2018",
            "doi": "10.9999/epmc",
            "pmid": "55555",
            "authorString": "Smith J, Doe A",
            "journalTitle": "PLoS One",
            "abstractText": "We analyzed the proteome...",
        }
        paper = EuropePmcRawResult.model_validate(raw).to_parsed_paper()
        assert isinstance(paper, ParsedPaper)
        assert paper.title == "EPMC Paper"
        assert paper.year == 2018
        assert paper.doi == "10.9999/epmc"
        assert paper.pmid == "55555"
        assert paper.authors == ["Smith J", "Doe A"]
        assert paper.journal_title == "PLoS One"
        assert paper.abstract == "We analyzed the proteome..."
        assert paper.snippet == "PLoS One"

    def test_to_parsed_paper_snippet_fallback(self) -> None:
        raw = {"title": "No Journal, No Abstract"}
        paper = EuropePmcRawResult.model_validate(raw).to_parsed_paper()
        assert paper.snippet is None
