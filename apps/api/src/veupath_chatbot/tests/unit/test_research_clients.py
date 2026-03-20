"""Tests for research API clients (arxiv, crossref, europepmc, openalex, pubmed, semanticscholar, preprint).

Each client is tested for:
- Successful response parsing
- Empty results
- HTTP error handling
- Citation generation
"""

import httpx
import pytest
import respx

from veupath_chatbot.platform.errors import ExternalServiceError

from veupath_chatbot.services.research.clients.arxiv import ArxivClient
from veupath_chatbot.services.research.clients.crossref import CrossrefClient
from veupath_chatbot.services.research.clients.europepmc import EuropePmcClient
from veupath_chatbot.services.research.clients.openalex import OpenAlexClient
from veupath_chatbot.services.research.clients.preprint import PreprintClient
from veupath_chatbot.services.research.clients.pubmed import PubmedClient
from veupath_chatbot.services.research.clients.semanticscholar import (
    SemanticScholarClient,
)

# ===========================================================================
# ArxivClient
# ===========================================================================


class TestArxivClient:
    @respx.mock
    async def test_search_parses_xml_entries(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Malaria Gene Expression Study</title>
                <link href="https://arxiv.org/abs/1234.5678" />
                <summary>This paper studies gene expression in Plasmodium.</summary>
            </entry>
        </feed>"""
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = ArxivClient(timeout_seconds=5.0)
        result = await client.search("malaria", limit=5, abstract_max_chars=500)

        assert result["source"] == "arxiv"
        assert result["query"] == "malaria"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["title"] == "Malaria Gene Expression Study"
        assert results[0]["url"] == "https://arxiv.org/abs/1234.5678"
        assert "gene expression" in results[0]["snippet"].lower()

    @respx.mock
    async def test_search_empty_feed(self) -> None:
        xml = '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = ArxivClient(timeout_seconds=5.0)
        result = await client.search("nothing", limit=5, abstract_max_chars=500)

        assert result["results"] == []
        citations = result["citations"]
        assert isinstance(citations, list)
        assert len(citations) == 0

    @respx.mock
    async def test_search_generates_citations(self) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Test Paper</title>
                <link href="https://arxiv.org/abs/9999.0001" />
                <summary>Abstract text.</summary>
            </entry>
        </feed>"""
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = ArxivClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)

        citations = result["citations"]
        assert isinstance(citations, list)
        assert len(citations) == 1
        c = citations[0]
        assert isinstance(c, dict)
        assert c["source"] == "arxiv"
        assert c["title"] == "Test Paper"
        assert c["url"] == "https://arxiv.org/abs/9999.0001"
        assert "tag" in c

    @respx.mock
    async def test_search_respects_limit(self) -> None:
        entries = "\n".join(
            f"<entry><title>Paper {i}</title><link href='https://arxiv.org/abs/{i}' /><summary>Abstract {i}</summary></entry>"
            for i in range(10)
        )
        xml = f'<?xml version="1.0" encoding="UTF-8"?><feed>{entries}</feed>'
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=xml)
        )
        client = ArxivClient(timeout_seconds=5.0)
        result = await client.search("test", limit=3, abstract_max_chars=500)

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 3

    @respx.mock
    async def test_search_http_error_raises(self) -> None:
        respx.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(500)
        )
        client = ArxivClient(timeout_seconds=5.0)
        with pytest.raises(ExternalServiceError):
            await client.search("test", limit=5, abstract_max_chars=500)


# ===========================================================================
# CrossrefClient
# ===========================================================================


class TestCrossrefClient:
    @respx.mock
    async def test_search_parses_items(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
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
                        ]
                    }
                },
            )
        )
        client = CrossrefClient(timeout_seconds=5.0)
        result = await client.search("plasmodium", limit=5, abstract_max_chars=500)

        assert result["source"] == "crossref"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "Plasmodium falciparum proteome"
        assert item["doi"] == "10.1234/test"
        assert item["year"] == 2020
        assert item["authors"] == ["John Smith", "Jane Doe"]
        assert item["journalTitle"] == "Nature"

    @respx.mock
    async def test_search_empty_results(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(200, json={"message": {"items": []}})
        )
        client = CrossrefClient(timeout_seconds=5.0)
        result = await client.search("nothing", limit=5, abstract_max_chars=500)

        assert result["results"] == []
        assert result["citations"] == []

    @respx.mock
    async def test_search_family_only_author(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
                                "title": ["Test"],
                                "DOI": "10.1/x",
                                "author": [{"family": "Solo"}],
                            }
                        ]
                    }
                },
            )
        )
        client = CrossrefClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["authors"] == ["Solo"]

    @respx.mock
    async def test_search_no_date_parts(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
                                "title": ["No Date"],
                                "DOI": "10.1/nd",
                            }
                        ]
                    }
                },
            )
        )
        client = CrossrefClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["year"] is None

    @respx.mock
    async def test_search_constructs_url_from_doi(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={"message": {"items": [{"title": ["T"], "DOI": "10.1/x"}]}},
            )
        )
        client = CrossrefClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["url"] == "https://doi.org/10.1/x"

    @respx.mock
    async def test_search_http_error_raises(self) -> None:
        respx.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(503)
        )
        client = CrossrefClient(timeout_seconds=5.0)
        with pytest.raises(ExternalServiceError):
            await client.search("test", limit=5, abstract_max_chars=500)


# ===========================================================================
# EuropePmcClient
# ===========================================================================


class TestEuropePmcClient:
    @respx.mock
    async def test_search_parses_results(self) -> None:
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "Gametocyte proteome analysis",
                                "pubYear": "2018",
                                "doi": "10.9999/epmc",
                                "pmid": "55555",
                                "authorString": "Smith J, Doe A",
                                "journalTitle": "PLoS One",
                                "abstractText": "We analyzed the proteome...",
                            }
                        ]
                    }
                },
            )
        )
        client = EuropePmcClient(timeout_seconds=5.0)
        result = await client.search("gametocyte", limit=5, abstract_max_chars=500)

        assert result["source"] == "europepmc"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "Gametocyte proteome analysis"
        assert item["year"] == 2018
        assert item["doi"] == "10.9999/epmc"
        assert item["pmid"] == "55555"
        assert item["authors"] == ["Smith J", "Doe A"]
        assert item["journalTitle"] == "PLoS One"

    @respx.mock
    async def test_search_constructs_doi_url(self) -> None:
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={"resultList": {"result": [{"title": "T", "doi": "10.1/x"}]}},
            )
        )
        client = EuropePmcClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["url"] == "https://doi.org/10.1/x"

    @respx.mock
    async def test_search_constructs_pubmed_url_when_no_doi(self) -> None:
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={"resultList": {"result": [{"title": "T", "pmid": "999"}]}},
            )
        )
        client = EuropePmcClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["url"] == "https://pubmed.ncbi.nlm.nih.gov/999/"

    @respx.mock
    async def test_search_year_as_int(self) -> None:
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={"resultList": {"result": [{"title": "T", "pubYear": 2020}]}},
            )
        )
        client = EuropePmcClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["year"] == 2020

    @respx.mock
    async def test_search_empty_results(self) -> None:
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(200, json={"resultList": {"result": []}})
        )
        client = EuropePmcClient(timeout_seconds=5.0)
        result = await client.search("nothing", limit=5, abstract_max_chars=500)
        assert result["results"] == []


# ===========================================================================
# OpenAlexClient
# ===========================================================================


class TestOpenAlexClient:
    @respx.mock
    async def test_search_parses_results(self) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
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
                    ]
                },
            )
        )
        client = OpenAlexClient(timeout_seconds=5.0)
        result = await client.search("malaria", limit=5, abstract_max_chars=500)

        assert result["source"] == "openalex"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "OpenAlex paper"
        assert item["year"] == 2021
        assert item["doi"] == "10.1111/oa"  # stripped prefix
        assert item["authors"] == ["Alice Smith", "Bob Jones"]
        assert item["journalTitle"] == "Cell"
        assert item["abstract"] is not None
        assert "study" in item["abstract"]

    @respx.mock
    async def test_search_reconstructs_abstract_from_inverted_index(self) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Test",
                            "abstract_inverted_index": {
                                "hello": [0],
                                "world": [1],
                                "foo": [2],
                            },
                        }
                    ]
                },
            )
        )
        client = OpenAlexClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["abstract"] == "hello world foo"

    @respx.mock
    async def test_search_empty_results(self) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        client = OpenAlexClient(timeout_seconds=5.0)
        result = await client.search("nothing", limit=5, abstract_max_chars=500)
        assert result["results"] == []

    @respx.mock
    async def test_search_no_doi_uses_openalex_id(self) -> None:
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "No DOI",
                            "id": "https://openalex.org/W456",
                        }
                    ]
                },
            )
        )
        client = OpenAlexClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["url"] == "https://openalex.org/W456"


# ===========================================================================
# SemanticScholarClient
# ===========================================================================


class TestSemanticScholarClient:
    @respx.mock
    async def test_search_parses_data(self) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "S2 Paper",
                            "year": 2022,
                            "url": "https://semanticscholar.org/paper/123",
                            "authors": [{"name": "Eve"}, {"name": "Frank"}],
                            "abstract": "This is the abstract.",
                            "journal": {"name": "Science"},
                            "externalIds": {
                                "DOI": "10.5555/s2",
                                "PubMed": "77777",
                            },
                        }
                    ]
                },
            )
        )
        client = SemanticScholarClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)

        assert result["source"] == "semanticscholar"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "S2 Paper"
        assert item["year"] == 2022
        assert item["doi"] == "10.5555/s2"
        assert item["pmid"] == "77777"
        assert item["authors"] == ["Eve", "Frank"]
        assert item["journalTitle"] == "Science"
        assert item["abstract"] is not None

    @respx.mock
    async def test_search_empty_data(self) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        client = SemanticScholarClient(timeout_seconds=5.0)
        result = await client.search("nothing", limit=5, abstract_max_chars=500)
        assert result["results"] == []

    @respx.mock
    async def test_search_no_external_ids(self) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "No IDs",
                            "year": 2023,
                            "url": "https://s2.org/1",
                        }
                    ]
                },
            )
        )
        client = SemanticScholarClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["doi"] is None
        assert item["pmid"] is None
        assert item["url"] == "https://s2.org/1"

    @respx.mock
    async def test_search_url_falls_back_to_doi(self) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "DOI only",
                            "externalIds": {"DOI": "10.1/x"},
                        }
                    ]
                },
            )
        )
        client = SemanticScholarClient(timeout_seconds=5.0)
        result = await client.search("test", limit=5, abstract_max_chars=500)
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["url"] == "https://doi.org/10.1/x"

    @respx.mock
    async def test_search_http_error_raises(self) -> None:
        respx.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(429)
        )
        client = SemanticScholarClient(timeout_seconds=5.0)
        with pytest.raises(ExternalServiceError):
            await client.search("test", limit=5, abstract_max_chars=500)


# ===========================================================================
# PubmedClient
# ===========================================================================


class TestPubmedClient:
    @respx.mock
    async def test_search_with_abstracts(self) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": ["99999"]}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": {
                        "99999": {
                            "title": "PubMed paper.",
                            "pubdate": "2021 Jun",
                            "authors": [{"name": "Doe J"}],
                            "fulljournalname": "The Lancet",
                        }
                    }
                },
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(
                200,
                text=(
                    "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
                    "<PMID>99999</PMID><Article><Abstract>"
                    "<AbstractText>Detailed abstract content here.</AbstractText>"
                    "</Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
                ),
            )
        )
        client = PubmedClient(timeout_seconds=5.0)
        result = await client.search(
            "test", limit=5, include_abstract=True, abstract_max_chars=500
        )

        assert result["source"] == "pubmed"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "PubMed paper."
        assert item["year"] == 2021
        assert item["pmid"] == "99999"
        assert item["authors"] == ["Doe J"]
        assert item["journalTitle"] == "The Lancet"
        assert item["abstract"] == "Detailed abstract content here."
        assert item["url"] == "https://pubmed.ncbi.nlm.nih.gov/99999/"

    @respx.mock
    async def test_search_without_abstracts(self) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": ["11111"]}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": {
                        "11111": {
                            "title": "No Abstract Paper",
                            "pubdate": "2019 Jan",
                            "authors": [],
                            "fulljournalname": "BMJ",
                        }
                    }
                },
            )
        )
        client = PubmedClient(timeout_seconds=5.0)
        result = await client.search(
            "test", limit=5, include_abstract=False, abstract_max_chars=500
        )

        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["abstract"] is None

    @respx.mock
    async def test_search_no_pmids_returns_empty(self) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
        )
        client = PubmedClient(timeout_seconds=5.0)
        result = await client.search(
            "nothing", limit=5, include_abstract=False, abstract_max_chars=500
        )

        assert result["results"] == []
        assert result["citations"] == []

    @respx.mock
    async def test_search_year_parsing(self) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": ["22222"]}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": {
                        "22222": {
                            "title": "Year Test",
                            "pubdate": "2023 Mar 15",
                            "authors": [],
                            "fulljournalname": "J",
                        }
                    }
                },
            )
        )
        client = PubmedClient(timeout_seconds=5.0)
        result = await client.search(
            "test", limit=5, include_abstract=False, abstract_max_chars=500
        )
        item = result["results"][0]
        assert isinstance(item, dict)
        assert item["year"] == 2023

    @respx.mock
    async def test_search_generates_citations(self) -> None:
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": ["33333"]}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": {
                        "33333": {
                            "title": "Citation Test",
                            "pubdate": "2020",
                            "authors": [{"name": "Smith A"}],
                            "fulljournalname": "J",
                        }
                    }
                },
            )
        )
        client = PubmedClient(timeout_seconds=5.0)
        result = await client.search(
            "test", limit=5, include_abstract=False, abstract_max_chars=500
        )
        citations = result["citations"]
        assert isinstance(citations, list)
        assert len(citations) == 1
        c = citations[0]
        assert isinstance(c, dict)
        assert c["source"] == "pubmed"
        assert c["pmid"] == "33333"


# ===========================================================================
# PreprintClient
# ===========================================================================


class TestPreprintClient:
    @respx.mock
    async def test_search_parses_ddg_html(self) -> None:
        html = '<html><body><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.biorxiv.org%2Fcontent%2F123">BioRxiv Paper Title</a></body></html>'
        respx.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text=html)
        )
        client = PreprintClient(timeout_seconds=5.0)
        result = await client.search(
            "malaria",
            site="biorxiv.org",
            source="biorxiv",
            limit=5,
            include_abstract=False,
            abstract_max_chars=500,
        )

        assert result["source"] == "biorxiv"
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        assert item["title"] == "BioRxiv Paper Title"
        assert item["url"] == "https://www.biorxiv.org/content/123"

    @respx.mock
    async def test_search_empty_results(self) -> None:
        respx.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html></html>")
        )
        client = PreprintClient(timeout_seconds=5.0)
        result = await client.search(
            "nothing",
            site="medrxiv.org",
            source="medrxiv",
            limit=5,
            include_abstract=False,
            abstract_max_chars=500,
        )
        assert result["results"] == []

    @respx.mock
    async def test_search_with_abstract_fetches_summaries(self) -> None:
        ddg_html = """<html><body>
        <a class="result__a" href="https://www.biorxiv.org/content/paper1">Paper One</a>
        </body></html>"""
        respx.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text=ddg_html)
        )
        respx.get("https://www.biorxiv.org/content/paper1").mock(
            return_value=httpx.Response(
                200,
                text='<html><head><meta name="description" content="This is the paper abstract from the meta tag."></head><body></body></html>',
            )
        )
        client = PreprintClient(timeout_seconds=5.0)
        result = await client.search(
            "test",
            site="biorxiv.org",
            source="biorxiv",
            limit=5,
            include_abstract=True,
            abstract_max_chars=500,
        )
        item = result["results"][0]
        assert isinstance(item, dict)
        abstract = item.get("abstract")
        assert isinstance(abstract, str)
        assert "paper abstract" in abstract.lower()

    @respx.mock
    async def test_search_respects_limit(self) -> None:
        links = "\n".join(
            f'<a class="result__a" href="https://biorxiv.org/paper/{i}">Paper {i}</a>'
            for i in range(10)
        )
        respx.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text=f"<html><body>{links}</body></html>")
        )
        client = PreprintClient(timeout_seconds=5.0)
        result = await client.search(
            "test",
            site="biorxiv.org",
            source="biorxiv",
            limit=3,
            include_abstract=False,
            abstract_max_chars=500,
        )
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 3

    @respx.mock
    async def test_search_generates_citations(self) -> None:
        html = '<html><body><a class="result__a" href="https://medrxiv.org/p1">MedRxiv Paper</a></body></html>'
        respx.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text=html)
        )
        client = PreprintClient(timeout_seconds=5.0)
        result = await client.search(
            "test",
            site="medrxiv.org",
            source="medrxiv",
            limit=5,
            include_abstract=False,
            abstract_max_chars=500,
        )
        citations = result["citations"]
        assert isinstance(citations, list)
        assert len(citations) == 1
        c = citations[0]
        assert isinstance(c, dict)
        assert c["source"] == "medrxiv"
        assert "tag" in c
