"""Live integration tests for GeneToolsMixin — no mocks, real VEuPathDB APIs.

Tests the AI tool wrappers (``lookup_gene_records`` and
``resolve_gene_ids_to_records``) end-to-end against live WDK/site-search.

Run::

    pytest src/veupath_chatbot/tests/integration/test_live_gene_tools.py -v -s

Skip with::

    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator

import pytest

from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search import close_site_search_client

pytestmark = pytest.mark.live_wdk


# ---------------------------------------------------------------------------
# Minimal concrete subclass — no mocks, just a real site_id
# ---------------------------------------------------------------------------


class _LiveTools(GeneToolsMixin):
    def __init__(self, site_id: str = "plasmodb") -> None:
        self.site_id = site_id


# ---------------------------------------------------------------------------
# Fixture: close HTTP clients after each test to avoid stale event loops
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_clients() -> AsyncGenerator[None]:
    yield
    await close_site_search_client()
    try:
        router = get_site_router()
        await router.close_all()
    except Exception:
        pass


# ===================================================================
# 1. lookup_gene_records — text search
# ===================================================================


class TestLookupGeneRecordsLive:
    """Test ``lookup_gene_records`` against real PlasmoDB site-search."""

    async def test_returns_results_for_known_gene(self) -> None:
        """PfCRT is a well-known P. falciparum gene — must return results."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="PfCRT")

        records = result.get("records")
        assert isinstance(records, list), (
            f"Expected 'records' key, got keys: {sorted(result.keys())}"
        )
        assert len(records) > 0, "PfCRT should return at least one gene"
        assert result["totalCount"] > 0

    async def test_returns_results_for_kinase_search(self) -> None:
        """'kinase' is a broad query — must return multiple genes."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=5)

        records = result.get("records")
        assert isinstance(records, list), (
            f"Expected 'records' key, got keys: {sorted(result.keys())}"
        )
        assert len(records) > 0

    async def test_result_shape_has_required_fields(self) -> None:
        """Each gene record must have geneId, organism, and product."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="AP2-G", limit=3)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0

        for rec in records:
            assert isinstance(rec, dict)
            assert "geneId" in rec, f"Missing geneId in record: {rec}"
            assert "organism" in rec
            assert "product" in rec
            assert "displayName" in rec

    async def test_organism_filter_returns_plasmodium_results(self) -> None:
        """When organism is specified, results should be filtered."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(
            query="kinase",
            organism="Plasmodium falciparum 3D7",
            limit=5,
        )

        records = result.get("records")
        assert isinstance(records, list), (
            f"Expected 'records' key, got keys: {sorted(result.keys())}"
        )
        # With an explicit organism filter, results should be Plasmodium
        for rec in records:
            assert isinstance(rec, dict)
            org = str(rec.get("organism", "")).lower()
            assert "plasmodium" in org or "falciparum" in org, (
                f"Expected Plasmodium organism, got: {rec.get('organism')}"
            )

    async def test_limit_respected(self) -> None:
        """Limit parameter should cap the number of results."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=3)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) <= 3

    async def test_works_across_sites(self) -> None:
        """Gene lookup should work on ToxoDB too."""
        tools = _LiveTools("toxodb")
        result = await tools.lookup_gene_records(query="SAG1", limit=5)

        records = result.get("records")
        assert isinstance(records, list), (
            f"Expected 'records' key, got keys: {sorted(result.keys())}"
        )
        assert len(records) > 0, "SAG1 should return results on ToxoDB"


# ===================================================================
# 2. resolve_gene_ids_to_records — ID resolution
# ===================================================================


class TestResolveGeneIdsToRecordsLive:
    """Test ``resolve_gene_ids_to_records`` against real PlasmoDB WDK."""

    async def test_resolves_known_gene_id(self) -> None:
        """PF3D7_1222600 (AP2-G) should resolve to a full record."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 1
        assert result["totalCount"] == 1

        rec = records[0]
        assert rec["geneId"] == "PF3D7_1222600"
        assert rec["product"]  # Should have a product name
        assert rec["organism"]  # Should have an organism

    async def test_resolves_multiple_gene_ids(self) -> None:
        """Multiple known gene IDs should all resolve."""
        tools = _LiveTools("plasmodb")
        gene_ids = ["PF3D7_1222600", "PF3D7_1031000", "PF3D7_0709000"]
        result = await tools.resolve_gene_ids_to_records(gene_ids=gene_ids)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == len(gene_ids)
        returned_ids = {str(r["geneId"]) for r in records}
        for gid in gene_ids:
            assert gid in returned_ids, f"Missing gene {gid} in results"

    async def test_nonexistent_gene_returns_empty(self) -> None:
        """A fake gene ID should resolve to zero records."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["FAKE_GENE_12345"],
        )

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 0

    async def test_result_shape_has_required_fields(self) -> None:
        """Each resolved record must have geneId, organism, product."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 1

        rec = records[0]
        assert "geneId" in rec
        assert "organism" in rec
        assert "product" in rec
        assert "displayName" in rec
        assert "geneName" in rec

    async def test_works_on_toxodb(self) -> None:
        """Gene resolution should work on ToxoDB too."""
        tools = _LiveTools("toxodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["TGME49_200010"],
        )

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0]["geneId"] == "TGME49_200010"


# ===================================================================
# 3. Response shape consistency
# ===================================================================


class TestResponseShapeConsistency:
    """Both tools must use the same response key for gene data."""

    async def test_lookup_uses_records_key(self) -> None:
        """lookup_gene_records must return data under 'records', not 'results'."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=3)

        assert "records" in result, (
            f"Expected 'records' key in lookup response, got: {sorted(result.keys())}"
        )
        assert "results" not in result, (
            "lookup_gene_records should use 'records' key, not 'results'"
        )

    async def test_resolve_uses_records_key(self) -> None:
        """resolve_gene_ids_to_records must return data under 'records'."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        assert "records" in result
        assert "results" not in result

    async def test_both_tools_have_total_count(self) -> None:
        """Both tools must include a 'totalCount' field."""
        tools = _LiveTools("plasmodb")

        lookup_result = await tools.lookup_gene_records(query="kinase", limit=3)
        assert "totalCount" in lookup_result
        assert isinstance(lookup_result["totalCount"], int)

        resolve_result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )
        assert "totalCount" in resolve_result
        assert isinstance(resolve_result["totalCount"], int)
