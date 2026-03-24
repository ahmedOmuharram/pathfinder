"""Integration tests for gene-ID enrichment against PlasmoDB WDK.

Tests the EXACT code path that was failing with "Either step_id or
search_name+parameters required" when a user pastes gene IDs (no WDK
search_name, no step_id) and requests enrichment.

The fix: _phase_enrich detects gene-ID experiments (step_id=None,
search_name="", target_gene_ids present) and builds a temporary
GeneByLocusTag dataset, then runs enrichment against that.

Record cassettes:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... \
    uv run pytest src/veupath_chatbot/tests/integration/test_live_gene_id_enrichment.py -v --record-mode=all

Replay (CI / normal dev):
    uv run pytest src/veupath_chatbot/tests/integration/test_live_gene_id_enrichment.py -v
"""

import pytest

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.enrichment.service import EnrichmentService
from veupath_chatbot.services.gene_sets.operations import (
    _build_enrichment_params_from_gene_ids,
)

SITE_ID = "plasmodb"

# Real P. falciparum gene IDs — known to exist in PlasmoDB.
# Mix of well-characterized genes so enrichment should find GO terms.
GENE_IDS = [
    "PF3D7_1222600",  # PfAP2-G - master regulator of sexual commitment
    "PF3D7_1031000",  # Pfs25 - surface antigen, TBV candidate
    "PF3D7_0209000",  # Pfs230 - gamete fertility factor
    "PF3D7_1346700",  # Pfs48/45 - TBV candidate
    "PF3D7_1346800",  # Pfs47 - female gamete fertility
    "PF3D7_0935400",  # CDPK4 - male gametocyte kinase
    "PF3D7_0406200",  # MDV1/PEG3 - male gametocyte development
    "PF3D7_1408200",  # Pf11-1 - gametocyte-specific
    "PF3D7_1216500",  # GEP1 - gametocyte egress protein
    "PF3D7_1477700",  # HAP2/GCS1 - male gamete fusion factor
]


class TestBuildEnrichmentParamsFromGeneIds:
    """Test _build_enrichment_params_from_gene_ids against live PlasmoDB.

    This creates a real WDK dataset from gene IDs and returns params
    suitable for enrichment. This was the missing link — gene-ID
    experiments had no way to get enrichment params.
    """

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_creates_dataset_and_returns_params(self) -> None:
        """Upload gene IDs to PlasmoDB, get back GeneByLocusTag params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(SITE_ID, GENE_IDS)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        # The dataset ID should be a non-empty string
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_small_gene_list(self) -> None:
        """Even a single gene should produce valid params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(SITE_ID, [GENE_IDS[0]])

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters


class TestEnrichmentServiceWithGeneIds:
    """Test the full enrichment pipeline: gene IDs → dataset → enrichment.

    This is the EXACT flow that was broken. Previously, gene-ID experiments
    passed step_id=None and search_name="" to EnrichmentService.run_batch(),
    which raised ValueError. Now _phase_enrich builds GeneByLocusTag params
    first, then passes those to run_batch().
    """

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_go_process_enrichment(self) -> None:
        """Build params from gene IDs, then run GO Process enrichment."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(SITE_ID, GENE_IDS)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id=SITE_ID,
            analysis_types=["go_process"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for r in results:
            if r.terms:
                r.terms[0]

        assert len(results) == 1
        result = results[0]
        assert result.analysis_type == "go_process"
        assert result.error is None
        # Should find GO terms for these well-characterized gametocyte genes
        assert len(result.terms) > 0, (
            "Expected at least one enriched GO term for known gametocyte genes"
        )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_multiple_enrichment_types(self) -> None:
        """Run GO Process + GO Function enrichment together."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(SITE_ID, GENE_IDS)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id=SITE_ID,
            analysis_types=["go_process", "go_function"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for _r in results:
            pass

        assert len(results) == 2
        types = {r.analysis_type for r in results}
        assert "go_process" in types
        assert "go_function" in types

    @pytest.mark.asyncio
    async def test_without_build_params_raises(self) -> None:
        """Verify that passing empty search_name + None step_id still raises.

        This confirms the original bug exists and our fix is necessary.
        """
        svc = EnrichmentService()
        with pytest.raises(ValidationError, match="step_id or search_name"):
            await svc.run_batch(
                site_id=SITE_ID,
                analysis_types=["go_process"],
                step_id=None,
                search_name="",
                parameters={},
            )
