"""VCR-backed integration tests for the discovery service module.

Replaces mock-based tests from unit/test_discovery.py that test happy-path
catalog loading, search lookup, and DiscoveryService orchestration against
real WDK API responses captured in cassettes.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_discovery.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_discovery.py -v
"""

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.discovery import (
    DiscoveryService,
    SearchCatalog,
)
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse

# ---------------------------------------------------------------------------
# SearchCatalog.load — real WDK expanded record types
# ---------------------------------------------------------------------------


class TestSearchCatalogLoadReal:
    """Test loading catalogs from real WDK responses (VCR-backed)."""

    @pytest.mark.vcr
    async def test_load_catalog(
        self, wdk_site_id: str,
    ) -> None:
        """Load a full catalog and verify structure."""
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        record_types = catalog.get_record_types()
        assert len(record_types) > 0, f"{wdk_site_id} should have record types"

        rt_segments = [rt.url_segment for rt in record_types]
        assert "transcript" in rt_segments, f"{wdk_site_id} must have transcript record type"

        transcript_searches = catalog.get_searches("transcript")
        assert len(transcript_searches) > 0, f"{wdk_site_id} must have transcript searches"

        genes_by_taxon = catalog.find_search("transcript", "GenesByTaxon")
        assert genes_by_taxon is not None
        assert genes_by_taxon.url_segment == "GenesByTaxon"

    @pytest.mark.vcr
    async def test_load_does_not_reload_when_already_loaded(
        self, wdk_site_id: str,
    ) -> None:
        """Second load call should short-circuit."""
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)
        count_before = len(catalog.get_record_types())

        await catalog.load(client)
        count_after = len(catalog.get_record_types())
        assert count_before == count_after


# ---------------------------------------------------------------------------
# SearchCatalog — find_search / find_record_type_for_search
# ---------------------------------------------------------------------------


class TestSearchCatalogLookupReal:
    """Test catalog search lookups against real WDK data."""

    @pytest.mark.vcr
    async def test_find_search_returns_matching_search(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        result = catalog.find_search("transcript", "GenesByTaxon")
        assert result is not None
        assert result.url_segment == "GenesByTaxon"
        assert result.display_name, "GenesByTaxon should have a display name"

    @pytest.mark.vcr
    async def test_find_search_returns_none_for_missing(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        assert catalog.find_search("transcript", "NonexistentSearch12345") is None
        assert catalog.find_search("nonexistent_type", "GenesByTaxon") is None

    @pytest.mark.vcr
    async def test_find_record_type_for_search(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        result = catalog.find_record_type_for_search("GenesByTaxon")
        assert result == "transcript"

    @pytest.mark.vcr
    async def test_find_record_type_for_search_returns_none_for_unknown(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        result = catalog.find_record_type_for_search("NonexistentSearch99999")
        assert result is None


# ---------------------------------------------------------------------------
# SearchCatalog.get_search_details
# ---------------------------------------------------------------------------


class TestSearchCatalogDetailsReal:
    """Test search details retrieval against real WDK API."""

    @pytest.mark.vcr
    async def test_get_search_details_returns_response(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        result = await catalog.get_search_details(
            client, "transcript", "GenesByTaxon"
        )
        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"

    @pytest.mark.vcr
    async def test_get_search_details_caches_results(
        self, wdk_site_id: str,
    ) -> None:
        router = get_site_router()
        client = router.get_client(wdk_site_id)
        catalog = SearchCatalog(wdk_site_id)
        await catalog.load(client)

        r1 = await catalog.get_search_details(client, "transcript", "GenesByTaxon")
        r2 = await catalog.get_search_details(client, "transcript", "GenesByTaxon")
        assert r1 is r2, "Second call should return cached result"


# ---------------------------------------------------------------------------
# DiscoveryService orchestration
# ---------------------------------------------------------------------------


class TestDiscoveryServiceReal:
    """Test DiscoveryService against real WDK (VCR-backed)."""

    @pytest.mark.vcr
    async def test_get_catalog_creates_and_caches(
        self, wdk_site_id: str,
    ) -> None:
        service = DiscoveryService()
        c1 = await service.get_catalog(wdk_site_id)
        c2 = await service.get_catalog(wdk_site_id)
        assert c1 is c2

    @pytest.mark.vcr
    async def test_get_record_types_returns_real_types(
        self, wdk_site_id: str,
    ) -> None:
        service = DiscoveryService()
        rts = await service.get_record_types(wdk_site_id)
        assert len(rts) > 0
        rt_segments = [rt.url_segment for rt in rts]
        assert "transcript" in rt_segments

    @pytest.mark.vcr
    async def test_get_searches_returns_real_searches(
        self, wdk_site_id: str,
    ) -> None:
        service = DiscoveryService()
        searches = await service.get_searches(wdk_site_id, "transcript")
        assert len(searches) > 0
        url_segments = [s.url_segment for s in searches]
        assert "GenesByTaxon" in url_segments

    @pytest.mark.vcr
    async def test_get_search_details_returns_real_details(
        self, wdk_site_id: str,
    ) -> None:
        service = DiscoveryService()
        result = await service.get_search_details(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
        assert result.search_data.parameters is not None
        assert len(result.search_data.parameters) > 0
