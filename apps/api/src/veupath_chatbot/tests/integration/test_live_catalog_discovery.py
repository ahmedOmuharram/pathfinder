"""Live integration tests for catalog/search discovery across multiple VEuPathDB databases.

Tests the search catalog discovery service layer — record type listing, search
listing, fuzzy search, and record-type resolution — against REAL VEuPathDB
WDK API endpoints. NO MOCKS.

Databases under test: PlasmoDB, ToxoDB, CryptoDB, FungiDB, TriTrypDB, VectorBase.

Requires network access to *.org WDK sites.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_live_catalog_discovery.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.types import JSONArray
from veupath_chatbot.services.catalog.searches import (
    find_record_type_for_search,
    get_raw_record_types,
    get_raw_searches,
    list_searches,
    search_for_searches,
)

pytestmark = pytest.mark.live_wdk

# ---------------------------------------------------------------------------
# Databases under test
# ---------------------------------------------------------------------------

ALL_DBS = ["plasmodb", "toxodb", "cryptodb", "fungidb", "tritrypdb", "vectorbase"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK httpx clients after each test.

    The site_router caches httpx clients.  If we don't close them between
    tests, the next test may try to reuse connections from an event loop
    that asyncio has already torn down.
    """
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_url_segments(record_types: JSONArray) -> list[str]:
    """Extract urlSegment values from raw record type dicts."""
    segments: list[str] = []
    for rt in record_types:
        if isinstance(rt, dict):
            seg = rt.get("urlSegment")
            if isinstance(seg, str):
                segments.append(seg)
    return segments


def _search_names(searches: list[dict[str, str]]) -> list[str]:
    """Extract search names from list_searches results."""
    return [s["name"] for s in searches if "name" in s]


# ===========================================================================
# 1. Record Types — multi-DB
# ===========================================================================


class TestRecordTypesMultiDb:
    """Verify get_raw_record_types returns valid record type objects for each DB."""

    @pytest.mark.asyncio
    async def test_plasmodb_record_types(self) -> None:
        result = await get_raw_record_types("plasmodb")
        assert isinstance(result, list)
        assert len(result) > 0, "PlasmoDB should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, "PlasmoDB must have a 'transcript' record type"

    @pytest.mark.asyncio
    async def test_toxodb_record_types(self) -> None:
        result = await get_raw_record_types("toxodb")
        assert isinstance(result, list)
        assert len(result) > 0, "ToxoDB should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, "ToxoDB must have a 'transcript' record type"

    @pytest.mark.asyncio
    async def test_cryptodb_record_types(self) -> None:
        result = await get_raw_record_types("cryptodb")
        assert isinstance(result, list)
        assert len(result) > 0, "CryptoDB should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, "CryptoDB must have a 'transcript' record type"

    @pytest.mark.asyncio
    async def test_fungidb_record_types(self) -> None:
        result = await get_raw_record_types("fungidb")
        assert isinstance(result, list)
        assert len(result) > 0, "FungiDB should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, "FungiDB must have a 'transcript' record type"

    @pytest.mark.asyncio
    async def test_tritrypdb_record_types(self) -> None:
        result = await get_raw_record_types("tritrypdb")
        assert isinstance(result, list)
        assert len(result) > 0, "TriTrypDB should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, (
            "TriTrypDB must have a 'transcript' record type"
        )

    @pytest.mark.asyncio
    async def test_vectorbase_record_types(self) -> None:
        result = await get_raw_record_types("vectorbase")
        assert isinstance(result, list)
        assert len(result) > 0, "VectorBase should have at least one record type"

        segments = _extract_url_segments(result)
        assert "transcript" in segments, (
            "VectorBase must have a 'transcript' record type"
        )


# ===========================================================================
# 2. List Searches — multi-DB
# ===========================================================================


class TestListSearchesMultiDb:
    """Verify list_searches returns public transcript searches for each DB."""

    @pytest.mark.asyncio
    async def test_plasmodb_transcript_searches(self) -> None:
        result = await list_searches("plasmodb", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"PlasmoDB should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "PlasmoDB must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "PlasmoDB must have GeneByLocusTag"

    @pytest.mark.asyncio
    async def test_toxodb_transcript_searches(self) -> None:
        result = await list_searches("toxodb", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"ToxoDB should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "ToxoDB must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "ToxoDB must have GeneByLocusTag"

    @pytest.mark.asyncio
    async def test_cryptodb_transcript_searches(self) -> None:
        result = await list_searches("cryptodb", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"CryptoDB should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "CryptoDB must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "CryptoDB must have GeneByLocusTag"

    @pytest.mark.asyncio
    async def test_fungidb_transcript_searches(self) -> None:
        result = await list_searches("fungidb", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"FungiDB should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "FungiDB must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "FungiDB must have GeneByLocusTag"

    @pytest.mark.asyncio
    async def test_tritrypdb_transcript_searches(self) -> None:
        result = await list_searches("tritrypdb", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"TriTrypDB should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "TriTrypDB must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "TriTrypDB must have GeneByLocusTag"

    @pytest.mark.asyncio
    async def test_vectorbase_transcript_searches(self) -> None:
        result = await list_searches("vectorbase", "transcript")
        names = _search_names(result)

        assert len(result) >= 10, (
            f"VectorBase should have many transcript searches, got {len(result)}"
        )
        assert "GenesByTaxon" in names, "VectorBase must have GenesByTaxon"
        assert "GeneByLocusTag" in names, "VectorBase must have GeneByLocusTag"


# ===========================================================================
# 3. Fuzzy Search for Searches — multi-DB
# ===========================================================================


class TestSearchForSearchesMultiDb:
    """Verify search_for_searches finds relevant searches via fuzzy matching."""

    @pytest.mark.asyncio
    async def test_plasmodb_search_kinase(self) -> None:
        result = await search_for_searches("plasmodb", "transcript", "kinase")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "PlasmoDB should find kinase-related searches"
        for r in result:
            assert "name" in r, "Each result must have a 'name' key"
            assert "displayName" in r, "Each result must have a 'displayName' key"

    @pytest.mark.asyncio
    async def test_toxodb_search_go_term(self) -> None:
        result = await search_for_searches("toxodb", "transcript", "GO term")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "ToxoDB should find GO-term-related searches"
        for r in result:
            assert "name" in r
            assert "displayName" in r

    @pytest.mark.asyncio
    async def test_cryptodb_search_location(self) -> None:
        result = await search_for_searches("cryptodb", "transcript", "location")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "CryptoDB should find location-related searches"
        for r in result:
            assert "name" in r
            assert "displayName" in r

    @pytest.mark.asyncio
    async def test_fungidb_search_ortholog(self) -> None:
        result = await search_for_searches("fungidb", "transcript", "ortholog")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "FungiDB should find ortholog-related searches"
        for r in result:
            assert "name" in r
            assert "displayName" in r

    @pytest.mark.asyncio
    async def test_tritrypdb_search_domain(self) -> None:
        result = await search_for_searches("tritrypdb", "transcript", "domain")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "TriTrypDB should find domain-related searches"
        for r in result:
            assert "name" in r
            assert "displayName" in r

    @pytest.mark.asyncio
    async def test_vectorbase_search_expression(self) -> None:
        result = await search_for_searches("vectorbase", "transcript", "expression")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, "VectorBase should find expression-related searches"
        for r in result:
            assert "name" in r
            assert "displayName" in r


# ===========================================================================
# 4. Search for Searches — no record type filter
# ===========================================================================


class TestSearchForSearchesNoRecordType:
    """Verify search_for_searches works when record_type is None (broad search)."""

    @pytest.mark.asyncio
    async def test_plasmodb_broad_search(self) -> None:
        result = await search_for_searches("plasmodb", None, "RNA")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, (
            "PlasmoDB should find RNA-related searches across all record types"
        )
        for r in result:
            assert "name" in r
            assert "displayName" in r

    @pytest.mark.asyncio
    async def test_toxodb_broad_search(self) -> None:
        result = await search_for_searches("toxodb", None, "phenotype")
        for _ in result[:5]:
            pass

        assert isinstance(result, list)
        assert len(result) > 0, (
            "ToxoDB should find phenotype-related searches across all record types"
        )
        for r in result:
            assert "name" in r
            assert "displayName" in r


# ===========================================================================
# 5. Find Record Type for Search
# ===========================================================================


class TestFindRecordTypeForSearch:
    """Verify find_record_type_for_search resolves the owning record type."""

    @pytest.mark.asyncio
    async def test_plasmodb_genes_by_taxon(self) -> None:
        result = await find_record_type_for_search(
            SearchContext("plasmodb", "transcript", "GenesByTaxon")
        )
        assert result == "transcript"

    @pytest.mark.asyncio
    async def test_plasmodb_gene_by_locus_tag(self) -> None:
        result = await find_record_type_for_search(
            SearchContext("plasmodb", "transcript", "GeneByLocusTag")
        )
        assert result == "transcript"

    @pytest.mark.asyncio
    async def test_unknown_search_returns_fallback(self) -> None:
        """An unknown search name should return the provided fallback record type."""
        result = await find_record_type_for_search(
            SearchContext("plasmodb", "transcript", "NonexistentSearch123")
        )
        assert result == "transcript", (
            "Unknown search should fall back to the provided record type"
        )

    @pytest.mark.asyncio
    async def test_toxodb_genes_by_taxon(self) -> None:
        result = await find_record_type_for_search(
            SearchContext("toxodb", "transcript", "GenesByTaxon")
        )
        assert result == "transcript"

    @pytest.mark.asyncio
    async def test_fungidb_genes_by_taxon(self) -> None:
        result = await find_record_type_for_search(
            SearchContext("fungidb", "transcript", "GenesByTaxon")
        )
        assert result == "transcript"


# ===========================================================================
# 6. Raw Searches — structure verification
# ===========================================================================


class TestGetRawSearches:
    """Verify get_raw_searches returns well-structured raw WDK search objects."""

    @pytest.mark.asyncio
    async def test_plasmodb_raw_transcript_searches(self) -> None:
        result = await get_raw_searches("plasmodb", "transcript")
        assert isinstance(result, list)
        assert len(result) > 0, "PlasmoDB should have raw transcript searches"

        # Spot-check structure of first item
        first = result[0]
        assert isinstance(first, WDKSearch), "Each raw search should be a WDKSearch"
        assert first.url_segment, "Raw search must have url_segment"

    @pytest.mark.asyncio
    async def test_toxodb_raw_transcript_searches(self) -> None:
        result = await get_raw_searches("toxodb", "transcript")
        assert isinstance(result, list)
        assert len(result) > 0, "ToxoDB should have raw transcript searches"

        first = result[0]
        assert isinstance(first, WDKSearch), "Each raw search should be a WDKSearch"
        assert first.url_segment, "Raw search must have url_segment"


# ===========================================================================
# 7. Cross-DB Search Consistency
# ===========================================================================


class TestSearchConsistency:
    """Verify that core searches exist consistently across all VEuPathDB databases."""

    @pytest.mark.asyncio
    async def test_all_dbs_have_genes_by_taxon(self) -> None:
        """GenesByTaxon should exist in every VEuPathDB database."""
        missing: list[str] = []
        for db in ALL_DBS:
            result = await list_searches(db, "transcript")
            names = _search_names(result)
            if "GenesByTaxon" not in names:
                missing.append(db)

        assert not missing, f"GenesByTaxon missing from: {missing}"

    @pytest.mark.asyncio
    async def test_all_dbs_have_gene_by_locus_tag(self) -> None:
        """GeneByLocusTag should exist in every VEuPathDB database."""
        missing: list[str] = []
        for db in ALL_DBS:
            result = await list_searches(db, "transcript")
            names = _search_names(result)
            if "GeneByLocusTag" not in names:
                missing.append(db)

        assert not missing, f"GeneByLocusTag missing from: {missing}"

    @pytest.mark.asyncio
    async def test_all_dbs_have_genes_by_text(self) -> None:
        """GenesByText (or GenesByTextSearch) should exist in every VEuPathDB database."""
        missing: list[str] = []
        for db in ALL_DBS:
            result = await list_searches(db, "transcript")
            names = _search_names(result)
            has_text_search = any(
                n in ("GenesByText", "GenesByTextSearch") for n in names
            )
            if not has_text_search:
                missing.append(db)

        assert not missing, f"GenesByText/GenesByTextSearch missing from: {missing}"
