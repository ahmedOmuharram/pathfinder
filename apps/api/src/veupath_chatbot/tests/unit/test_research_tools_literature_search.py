import pytest
import respx
import httpx

from veupath_chatbot.ai.tools.research_tools import ResearchTools


@pytest.mark.asyncio
async def test_literature_search_all_sources_with_filters_year_and_author():
    tools = ResearchTools(timeout_seconds=5.0)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "Male gametocyte proteome in Plasmodium falciparum",
                                "pubYear": "2016",
                                "authorString": "Lasonder, X; Other, Y",
                                "doi": "10.1234/example",
                                "pmid": "12345678",
                                "journalTitle": "Nature",
                                "abstractText": "Male gametocytes ...",
                            },
                            {
                                "title": "Old unrelated paper",
                                "pubYear": "2001",
                                "authorString": "Someone, A",
                                "doi": "10.9999/old",
                                "pmid": "999",
                                "journalTitle": "Old Journal",
                            },
                        ]
                    }
                },
            )
        )
        router.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
                                "title": ["Another paper by Lasonder"],
                                "DOI": "10.1111/keep",
                                "URL": "https://doi.org/10.1111/keep",
                                "published-print": {"date-parts": [[2017, 1, 1]]},
                                "author": [{"given": "A", "family": "Lasonder"}],
                                "container-title": ["Science"],
                            },
                            {
                                "title": ["Filtered by year"],
                                "DOI": "10.1111/drop",
                                "URL": "https://doi.org/10.1111/drop",
                                "published-print": {"date-parts": [[1999, 1, 1]]},
                                "author": [{"given": "B", "family": "Lasonder"}],
                            },
                        ]
                    }
                },
            )
        )
        # New "all" sources (return empty in this test).
        router.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        router.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        router.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": []}}
            )
        )
        router.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(
                200,
                text=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
                ),
            )
        )
        # Preprint sources use DDG HTML (return empty).
        router.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html></html>")
        )

        out = await tools.literature_search(
            "gametocyte upregulated",
            source="all",
            limit=10,
            year_from=2015,
            author_includes="lasonder",
        )

    assert out["source"] == "all"
    assert out["sort"] == "relevance"
    assert "bySource" in out
    assert out["filters"]["yearFrom"] == 2015
    assert out["filters"]["authorIncludes"] == "lasonder"
    # Should keep the 2016 EuropePMC item and the 2017 Crossref item.
    titles = [r["title"] for r in out["results"]]
    assert any("proteome" in t.lower() for t in titles)
    assert any("another paper" in t.lower() for t in titles)
    # When source=all and sort=relevance, reranker adds a score.
    assert all(isinstance(r.get("score"), (int, float)) for r in out["results"])
    # Should filter out old items.
    assert all((r.get("year") or 0) >= 2015 for r in out["results"])
    # Citations are not limited to just the top-N displayed results.
    assert len(out["citations"]) >= len(out["results"])


@pytest.mark.asyncio
async def test_literature_search_all_sources_includes_citations_beyond_results_limit():
    tools = ResearchTools(timeout_seconds=5.0)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(200, json={"resultList": {"result": []}})
        )
        router.get("https://api.crossref.org/works").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
                                "title": ["Paper A"],
                                "DOI": "10.1111/a",
                                "URL": "https://doi.org/10.1111/a",
                                "published-print": {"date-parts": [[2017, 1, 1]]},
                                "author": [{"given": "A", "family": "One"}],
                                "container-title": ["J"],
                            },
                            {
                                "title": ["Paper B"],
                                "DOI": "10.1111/b",
                                "URL": "https://doi.org/10.1111/b",
                                "published-print": {"date-parts": [[2016, 1, 1]]},
                                "author": [{"given": "B", "family": "Two"}],
                                "container-title": ["J"],
                            },
                            {
                                "title": ["Paper C"],
                                "DOI": "10.1111/c",
                                "URL": "https://doi.org/10.1111/c",
                                "published-print": {"date-parts": [[2015, 1, 1]]},
                                "author": [{"given": "C", "family": "Three"}],
                                "container-title": ["J"],
                            },
                        ]
                    }
                },
            )
        )
        router.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        router.get("https://api.semanticscholar.org/graph/v1/paper/search").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        router.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
        )
        router.get("http://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(
                200,
                text='<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>',
            )
        )
        router.get("https://duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html></html>")
        )

        out = await tools.literature_search("paper", source="all", limit=1)

    assert len(out["results"]) == 1
    # But citations should include the other crossref items too.
    assert len(out["citations"]) >= 3


@pytest.mark.asyncio
async def test_literature_search_newest_sort_and_require_doi():
    tools = ResearchTools(timeout_seconds=5.0)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "title": "No DOI newer",
                                "pubYear": "2020",
                                "authorString": "Someone, A",
                                "pmid": "111",
                                "journalTitle": "J1",
                            },
                            {
                                "title": "Has DOI older",
                                "pubYear": "2019",
                                "authorString": "Someone, A",
                                "doi": "10.5555/keep",
                                "pmid": "222",
                                "journalTitle": "J2",
                            },
                        ]
                    }
                },
            )
        )

        out = await tools.literature_search(
            "x",
            source="europepmc",
            limit=10,
            sort="newest",
            require_doi=True,
        )

    assert out["sort"] == "newest"
    # require_doi should drop the 2020 result without DOI.
    assert len(out["results"]) == 1
    assert out["results"][0]["doi"] == "10.5555/keep"


@pytest.mark.asyncio
async def test_literature_search_include_abstract_pubmed_efetch():
    tools = ResearchTools(timeout_seconds=5.0)

    with respx.mock(assert_all_called=False) as router:
        router.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"idlist": ["12345"]}}
            )
        )
        router.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": {
                        "12345": {
                            "title": "Example paper.",
                            "pubdate": "2019 Jan",
                            "authors": [{"name": "Doe J"}],
                            "fulljournalname": "J",
                        }
                    }
                },
            )
        )
        router.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        ).mock(
            return_value=httpx.Response(
                200,
                text=(
                    "<PubmedArticleSet>"
                    "<PubmedArticle>"
                    "<MedlineCitation>"
                    "<PMID>12345</PMID>"
                    "<Article>"
                    "<Abstract>"
                    "<AbstractText>This is the abstract.</AbstractText>"
                    "</Abstract>"
                    "</Article>"
                    "</MedlineCitation>"
                    "</PubmedArticle>"
                    "</PubmedArticleSet>"
                ),
            )
        )

        out = await tools.literature_search(
            "x",
            source="pubmed",
            limit=1,
            include_abstract=True,
        )

    assert out["source"] == "pubmed"
    assert len(out["results"]) == 1
    assert out["results"][0].get("abstract") == "This is the abstract."

