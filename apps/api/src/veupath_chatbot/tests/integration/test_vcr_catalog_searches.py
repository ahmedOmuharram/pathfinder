"""VCR-backed integration tests for services/catalog/searches.py.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_catalog_searches.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_catalog_searches.py -v
"""

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.services.catalog.models import SearchMatch
from veupath_chatbot.services.catalog.searches import (
    find_record_type_for_search,
    list_searches,
    search_for_searches,
)

# ---------------------------------------------------------------------------
# list_searches — real WDK
# ---------------------------------------------------------------------------


class TestListSearchesReal:
    """Test list_searches against real WDK responses."""

    @pytest.mark.vcr
    async def test_basic_list(self, wdk_site_id: str) -> None:
        result = await list_searches(wdk_site_id, "transcript")
        assert len(result) > 0, f"{wdk_site_id} should have transcript searches"
        for entry in result:
            assert "name" in entry
            assert "displayName" in entry

    @pytest.mark.vcr
    async def test_contains_genes_by_taxon(self, wdk_site_id: str) -> None:
        result = await list_searches(wdk_site_id, "transcript")
        names = [s["name"] for s in result]
        assert "GenesByTaxon" in names

    @pytest.mark.vcr
    async def test_filters_internal_searches(self, wdk_site_id: str) -> None:
        """Internal searches (InternalQuestions.*) should be excluded."""
        result = await list_searches(wdk_site_id, "transcript")
        for entry in result:
            assert not entry["name"].startswith("InternalQuestions.")

    @pytest.mark.vcr
    async def test_empty_for_unknown_record_type(self, wdk_site_id: str) -> None:
        result = await list_searches(wdk_site_id, "nonexistent_record_type_xyz")
        assert result == []


# ---------------------------------------------------------------------------
# search_for_searches — real WDK
# ---------------------------------------------------------------------------


class TestSearchForSearchesReal:
    """Test search_for_searches against real WDK responses."""

    @pytest.mark.vcr
    async def test_finds_taxon_related_searches(self, wdk_site_id: str) -> None:
        result = await search_for_searches(wdk_site_id, "transcript", "taxon")
        assert len(result) > 0
        for r in result:
            assert isinstance(r, SearchMatch)
            assert r.name

    @pytest.mark.vcr
    async def test_filters_by_record_type(self, wdk_site_id: str) -> None:
        result = await search_for_searches(wdk_site_id, "transcript", "genes")
        assert len(result) > 0
        for r in result:
            assert isinstance(r, SearchMatch)

    @pytest.mark.vcr
    async def test_no_matches_for_gibberish(self, wdk_site_id: str) -> None:
        result = await search_for_searches(
            wdk_site_id, "transcript", "zzzznonexistent123456"
        )
        assert result == []

    @pytest.mark.vcr
    async def test_limits_results(self, wdk_site_id: str) -> None:
        result = await search_for_searches(wdk_site_id, "transcript", "gene")
        assert len(result) <= 20

    @pytest.mark.vcr
    async def test_broad_search_without_record_type(self, wdk_site_id: str) -> None:
        result = await search_for_searches(wdk_site_id, None, "ortholog")
        assert len(result) > 0
        for r in result:
            assert isinstance(r, SearchMatch)
            assert r.name
            assert r.display_name

    @pytest.mark.vcr
    async def test_search_results_have_display_name(self, wdk_site_id: str) -> None:
        result = await search_for_searches(wdk_site_id, "transcript", "taxon")
        for r in result:
            assert r.display_name, f"Search {r.name} should have a display name"


# ---------------------------------------------------------------------------
# find_record_type_for_search — real WDK
# ---------------------------------------------------------------------------


class TestFindRecordTypeForSearchReal:
    """Test find_record_type_for_search against real WDK catalog."""

    @pytest.mark.vcr
    async def test_genes_by_taxon_in_transcript(self, wdk_site_id: str) -> None:
        result = await find_record_type_for_search(
            SearchContext(wdk_site_id, "transcript", "GenesByTaxon")
        )
        assert result == "transcript"

    @pytest.mark.vcr
    async def test_unknown_search_falls_back(self, wdk_site_id: str) -> None:
        result = await find_record_type_for_search(
            SearchContext(wdk_site_id, "transcript", "NonexistentSearch99999")
        )
        assert result == "transcript"

    @pytest.mark.vcr
    async def test_gene_by_locus_tag_in_transcript(self, wdk_site_id: str) -> None:
        result = await find_record_type_for_search(
            SearchContext(wdk_site_id, "transcript", "GeneByLocusTag")
        )
        assert result == "transcript"
