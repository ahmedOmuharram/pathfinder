"""VCR-backed integration tests for GeneToolsMixin.

Tests the AI tool wrappers (``lookup_gene_records`` and
``resolve_gene_ids_to_records``) end-to-end against real WDK/site-search
responses captured in VCR cassettes.

Record cassettes::

    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... \
    uv run pytest src/veupath_chatbot/tests/integration/test_live_gene_tools.py -v --record-mode=all

Replay (default)::

    uv run pytest src/veupath_chatbot/tests/integration/test_live_gene_tools.py -v
"""

import contextlib
from collections.abc import AsyncGenerator

import pytest

from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.gene_lookup.lookup import GeneSearchResult
from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.wdk import GeneResolveResult

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
    with contextlib.suppress(Exception):
        router = get_site_router()
        await router.close_all()
    yield
    with contextlib.suppress(Exception):
        router = get_site_router()
        await router.close_all()


# ===================================================================
# 1. lookup_gene_records — text search
# ===================================================================


class TestLookupGeneRecordsLive:
    """Test ``lookup_gene_records`` against real PlasmoDB site-search."""

    @pytest.mark.vcr
    async def test_returns_results_for_known_gene(self) -> None:
        """PfCRT is a well-known P. falciparum gene — must return results."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="PfCRT")

        assert isinstance(result, GeneSearchResult)
        assert len(result.records) > 0, "PfCRT should return at least one gene"
        assert result.total_count > 0

    @pytest.mark.vcr
    async def test_returns_results_for_kinase_search(self) -> None:
        """'kinase' is a broad query — must return multiple genes."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=5)

        assert isinstance(result, GeneSearchResult)
        assert len(result.records) > 0

    @pytest.mark.vcr
    async def test_result_shape_has_required_fields(self) -> None:
        """Each gene record must have gene_id, organism, and product."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="AP2-G", limit=3)

        assert len(result.records) > 0

        for rec in result.records:
            assert isinstance(rec, GeneResult)
            assert rec.gene_id, f"Missing gene_id in record: {rec}"
            assert rec.organism
            assert rec.product
            assert rec.display_name

    @pytest.mark.vcr
    async def test_organism_filter_returns_plasmodium_results(self) -> None:
        """When organism is specified, results should be filtered."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(
            query="kinase",
            organism="Plasmodium falciparum 3D7",
            limit=5,
        )

        assert isinstance(result, GeneSearchResult)
        # With an explicit organism filter, results should be Plasmodium
        for rec in result.records:
            org = rec.organism.lower()
            assert "plasmodium" in org or "falciparum" in org, (
                f"Expected Plasmodium organism, got: {rec.organism}"
            )

    @pytest.mark.vcr
    async def test_limit_respected(self) -> None:
        """Limit parameter should cap the number of results."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=3)

        assert len(result.records) <= 3

    @pytest.mark.vcr
    async def test_works_across_sites(self) -> None:
        """Gene lookup should work on ToxoDB too."""
        tools = _LiveTools("toxodb")
        result = await tools.lookup_gene_records(query="SAG1", limit=5)

        assert isinstance(result, GeneSearchResult)
        assert len(result.records) > 0, "SAG1 should return results on ToxoDB"


# ===================================================================
# 2. resolve_gene_ids_to_records — ID resolution
# ===================================================================


class TestResolveGeneIdsToRecordsLive:
    """Test ``resolve_gene_ids_to_records`` against real PlasmoDB WDK."""

    @pytest.mark.vcr
    async def test_resolves_known_gene_id(self) -> None:
        """PF3D7_1222600 (AP2-G) should resolve to a full record."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        assert isinstance(result, GeneResolveResult)
        assert len(result.records) == 1
        assert result.total_count == 1

        rec = result.records[0]
        assert rec.gene_id == "PF3D7_1222600"
        assert rec.product  # Should have a product name
        assert rec.organism  # Should have an organism

    @pytest.mark.vcr
    async def test_resolves_multiple_gene_ids(self) -> None:
        """Multiple known gene IDs should all resolve."""
        tools = _LiveTools("plasmodb")
        gene_ids = ["PF3D7_1222600", "PF3D7_1031000", "PF3D7_0709000"]
        result = await tools.resolve_gene_ids_to_records(gene_ids=gene_ids)

        assert len(result.records) == len(gene_ids)
        returned_ids = {r.gene_id for r in result.records}
        for gid in gene_ids:
            assert gid in returned_ids, f"Missing gene {gid} in results"

    @pytest.mark.vcr
    async def test_nonexistent_gene_returns_empty(self) -> None:
        """A fake gene ID should resolve to zero records."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["FAKE_GENE_12345"],
        )

        assert len(result.records) == 0

    @pytest.mark.vcr
    async def test_result_shape_has_required_fields(self) -> None:
        """Each resolved record must have gene_id, organism, product."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        assert len(result.records) == 1

        rec = result.records[0]
        assert rec.gene_id
        assert rec.organism
        assert rec.product
        assert rec.display_name
        assert rec.gene_name is not None  # Field exists (may be empty)

    @pytest.mark.vcr
    async def test_works_on_toxodb(self) -> None:
        """Gene resolution should work on ToxoDB too."""
        tools = _LiveTools("toxodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["TGME49_200010"],
        )

        assert len(result.records) == 1
        assert result.records[0].gene_id == "TGME49_200010"


# ===================================================================
# 3. Response shape consistency
# ===================================================================


class TestResponseShapeConsistency:
    """Both tools return typed dataclasses with .records and .total_count."""

    @pytest.mark.vcr
    async def test_lookup_returns_gene_search_result(self) -> None:
        """lookup_gene_records must return a GeneSearchResult with .records."""
        tools = _LiveTools("plasmodb")
        result = await tools.lookup_gene_records(query="kinase", limit=3)

        assert isinstance(result, GeneSearchResult)
        assert isinstance(result.records, list)

    @pytest.mark.vcr
    async def test_resolve_returns_gene_resolve_result(self) -> None:
        """resolve_gene_ids_to_records must return a GeneResolveResult."""
        tools = _LiveTools("plasmodb")
        result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )

        assert isinstance(result, GeneResolveResult)
        assert isinstance(result.records, list)

    @pytest.mark.vcr
    async def test_both_tools_have_total_count(self) -> None:
        """Both tools must include a total_count field."""
        tools = _LiveTools("plasmodb")

        lookup_result = await tools.lookup_gene_records(query="kinase", limit=3)
        assert isinstance(lookup_result.total_count, int)

        resolve_result = await tools.resolve_gene_ids_to_records(
            gene_ids=["PF3D7_1222600"],
        )
        assert isinstance(resolve_result.total_count, int)
