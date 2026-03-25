"""VCR-backed integration tests for gene lookup across VEuPathDB databases.

All gene IDs and organism names are discovered dynamically from whichever
site the test is assigned to. No hardcoded gene lists.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_gene_lookup.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_gene_lookup.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.services.gene_lookup.wdk import (
    WDK_TEXT_FIELDS_BROAD,
    GeneResolveResult,
    fetch_wdk_text_genes,
    resolve_gene_ids,
)
from veupath_chatbot.tests.conftest import discover_gene_ids, discover_leaf_organism

# ===========================================================================
# 1. Resolve gene IDs — dynamic discovery
# ===========================================================================


class TestResolveGeneIdsVcr:
    """Resolve gene IDs against real WDK responses (cassette-backed)."""

    @pytest.mark.vcr
    async def test_resolves_discovered_gene_ids(
        self, wdk_api: StrategyAPI, wdk_site_id: str,
    ) -> None:
        """Discover gene IDs from the site, then resolve them."""
        gene_ids = await discover_gene_ids(wdk_api, limit=5)
        assert len(gene_ids) > 0, f"Should discover gene IDs from {wdk_site_id}"

        result = await resolve_gene_ids(wdk_site_id, gene_ids)

        assert isinstance(result, GeneResolveResult)
        assert result.total_count > 0
        assert len(result.records) > 0

    @pytest.mark.vcr
    async def test_resolves_single_gene(
        self, wdk_api: StrategyAPI, wdk_site_id: str,
    ) -> None:
        """Single gene ID resolves correctly."""
        gene_ids = await discover_gene_ids(wdk_api, limit=1)
        assert len(gene_ids) >= 1

        result = await resolve_gene_ids(wdk_site_id, [gene_ids[0]])

        assert isinstance(result, GeneResolveResult)
        assert result.total_count >= 1


# ===========================================================================
# 2. Text search — dynamic discovery
# ===========================================================================


class TestTextSearchVcr:
    """Text gene search against real WDK responses (cassette-backed)."""

    @pytest.mark.vcr
    async def test_kinase_text_search(
        self, wdk_api: StrategyAPI, wdk_site_id: str,
    ) -> None:
        """Search for 'kinase' genes on the assigned site."""
        organism = await discover_leaf_organism(wdk_api)

        result = await fetch_wdk_text_genes(
            wdk_site_id,
            ["kinase*"],
            organism=organism,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0


# ===========================================================================
# 3. Edge cases
# ===========================================================================


class TestResolveGeneIdsEdgeCasesVcr:
    """Edge-case gene resolution against real WDK (cassette-backed)."""

    @pytest.mark.vcr
    async def test_empty_gene_list(self, wdk_site_id: str) -> None:
        result = await resolve_gene_ids(wdk_site_id, [])

        assert isinstance(result, GeneResolveResult)
        assert result.total_count == 0
        assert len(result.records) == 0

    @pytest.mark.vcr
    async def test_nonexistent_gene_ids(self, wdk_site_id: str) -> None:
        result = await resolve_gene_ids(
            wdk_site_id,
            ["FAKE_GENE_001", "FAKE_GENE_002"],
        )

        assert isinstance(result, GeneResolveResult)
        assert isinstance(result.total_count, int)
