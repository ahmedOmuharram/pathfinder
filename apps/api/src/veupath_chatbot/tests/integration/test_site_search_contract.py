"""Integration tests for SiteSearchClient HTTP contract compliance.

Tests real site-search POST requests against VEuPathDB (backed by VCR
cassettes) to verify payload construction and response parsing.

Record cassettes:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... WDK_TARGET_SITE=plasmodb \
    uv run pytest src/veupath_chatbot/tests/integration/test_site_search_contract.py -v --record-mode=all

Replay (CI / normal dev):
    uv run pytest src/veupath_chatbot/tests/integration/test_site_search_contract.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
    SiteSearchClient,
    SiteSearchResponse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Site-search uses the origin (e.g. https://plasmodb.org), NOT the WDK
# service URL. Map site_id to origin + project_id.
_SITE_ORIGINS: dict[str, tuple[str, str]] = {
    "plasmodb": ("https://plasmodb.org", "PlasmoDB"),
    "toxodb": ("https://toxodb.org", "ToxoDB"),
    "cryptodb": ("https://cryptodb.org", "CryptoDB"),
    "giardiadb": ("https://giardiadb.org", "GiardiaDB"),
    "amoebadb": ("https://amoebadb.org", "AmoebaDB"),
    "microsporidiadb": ("https://microsporidiadb.org", "MicrosporidiaDB"),
    "piroplasmadb": ("https://piroplasmadb.org", "PiroplasmaDB"),
    "tritrypdb": ("https://tritrypdb.org", "TriTrypDB"),
    "trichdb": ("https://trichdb.org", "TrichDB"),
    "fungidb": ("https://fungidb.org", "FungiDB"),
    "vectorbase": ("https://vectorbase.org", "VectorBase"),
    "hostdb": ("https://hostdb.org", "HostDB"),
}


@pytest.fixture
async def site_search_client(
    wdk_test_site: tuple[str, str],
) -> SiteSearchClient:
    """Real SiteSearchClient for the test site, backed by VCR cassettes."""
    site_id, _base_url = wdk_test_site
    origin, project_id = _SITE_ORIGINS.get(
        site_id, ("https://plasmodb.org", "PlasmoDB")
    )
    client = SiteSearchClient(origin, project_id)
    yield client
    await client.close()


# ---------------------------------------------------------------------------
# Basic search
# ---------------------------------------------------------------------------


class TestSiteSearchBasic:
    """Verify basic site-search request/response cycle against real API."""

    @pytest.mark.vcr
    async def test_search_returns_typed_response(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Basic search returns a properly typed SiteSearchResponse."""
        resp = await site_search_client.search("kinase")

        assert isinstance(resp, SiteSearchResponse)
        assert resp.search_results.total_count > 0
        assert len(resp.search_results.documents) > 0

    @pytest.mark.vcr
    async def test_search_documents_have_expected_fields(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Documents in search results have key fields populated."""
        resp = await site_search_client.search("kinase", limit=5)

        for doc in resp.search_results.documents:
            assert doc.document_type != ""
            assert len(doc.primary_key) > 0

    @pytest.mark.vcr
    async def test_search_returns_organism_counts(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Site-search response includes organism counts when results exist."""
        resp = await site_search_client.search("kinase")

        # Organism counts may be empty for non-organism doc types, but for a
        # broad query like "kinase" on any VEuPathDB site, we expect counts.
        assert len(resp.organism_counts) > 0
        # Some organisms may have 0 count; at least one should be positive.
        assert any(count > 0 for count in resp.organism_counts.values())

    @pytest.mark.vcr
    async def test_search_returns_document_types(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Site-search response includes document type metadata."""
        resp = await site_search_client.search("kinase")

        assert len(resp.document_types) > 0
        # At least one should be a WDK record type (e.g. gene)
        wdk_types = [dt for dt in resp.document_types if dt.is_wdk_record_type]
        assert len(wdk_types) > 0
        for dt in wdk_types:
            assert dt.wdk_search_name is not None
            assert dt.id != ""

    @pytest.mark.vcr
    async def test_search_returns_categories(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Site-search response includes categories grouping document types."""
        resp = await site_search_client.search("kinase")

        assert len(resp.categories) > 0
        for cat in resp.categories:
            assert cat.name != ""

    @pytest.mark.vcr
    async def test_search_returns_field_counts_or_empty(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Site-search response includes field_counts field (may be empty).

        The site-search API does not always populate field_counts for
        unfiltered queries. The important thing is the field parses correctly.
        """
        resp = await site_search_client.search("kinase")

        # field_counts is always a dict (possibly empty)
        assert isinstance(resp.field_counts, dict)


# ---------------------------------------------------------------------------
# Filtered search
# ---------------------------------------------------------------------------


class TestSiteSearchFilters:
    """Verify filter parameters are sent correctly and produce valid responses."""

    @pytest.mark.vcr
    async def test_document_type_filter_restricts_results(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Filtering by document_type=gene returns only gene documents."""
        resp = await site_search_client.search(
            "kinase",
            document_type_filter=DocumentTypeFilter(document_type="gene"),
        )

        assert isinstance(resp, SiteSearchResponse)
        # All returned documents should be type "gene"
        for doc in resp.search_results.documents:
            assert doc.document_type == "gene"

    @pytest.mark.vcr
    async def test_pagination_controls_result_count(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Custom limit and offset control the result set."""
        resp = await site_search_client.search("kinase", limit=3, offset=0)

        assert isinstance(resp, SiteSearchResponse)
        assert len(resp.search_results.documents) <= 3

    @pytest.mark.vcr
    async def test_empty_search_uses_star(
        self,
        site_search_client: SiteSearchClient,
    ) -> None:
        """Empty search text is treated as wildcard and returns results."""
        resp = await site_search_client.search("")

        assert isinstance(resp, SiteSearchResponse)
        assert resp.search_results.total_count > 0
