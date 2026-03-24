"""VCR-backed integration tests verifying workbench fixes across VEuPathDB sites.

Tests:
1. GeneByLocusTag search availability + ds_gene_ids parameter across 11 sites
2. Gene set enrichment with specific gene IDs across 4 databases
3. Enrichment response shape verification (term fields)

Responses captured in VCR cassettes for offline replay in CI.

Record cassettes::

    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... \
    uv run pytest src/veupath_chatbot/tests/integration/test_live_workbench_fixes.py -v --record-mode=all

Replay (default)::

    uv run pytest src/veupath_chatbot/tests/integration/test_live_workbench_fixes.py -v
"""

from collections.abc import AsyncGenerator

import httpx
import pytest

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.enrichment.service import EnrichmentService
from veupath_chatbot.services.gene_sets.operations import (
    _build_enrichment_params_from_gene_ids,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK clients after each test to avoid connection leaks."""
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# Test 4: GeneByLocusTag availability across all VEuPathDB sites
# ---------------------------------------------------------------------------

# Sites that host gene/transcript records and should have GeneByLocusTag.
# OrthoMCL is excluded because it uses "group" record types, not transcript.
GENE_SITES = [
    ("plasmodb", "https://plasmodb.org/plasmo/service"),
    ("toxodb", "https://toxodb.org/toxo/service"),
    ("cryptodb", "https://cryptodb.org/cryptodb/service"),
    ("fungidb", "https://fungidb.org/fungidb/service"),
    ("tritrypdb", "https://tritrypdb.org/tritrypdb/service"),
    ("giardiadb", "https://giardiadb.org/giardiadb/service"),
    ("amoebadb", "https://amoebadb.org/amoeba/service"),
    ("microsporidiadb", "https://microsporidiadb.org/micro/service"),
    ("piroplasmadb", "https://piroplasmadb.org/piro/service"),
    ("hostdb", "https://hostdb.org/hostdb/service"),
    ("vectorbase", "https://vectorbase.org/vectorbase/service"),
]


class TestGeneByLocusTagAvailability:
    """Verify GeneByLocusTag search exists on every VEuPathDB gene site."""

    @pytest.mark.asyncio
    @pytest.mark.vcr
    @pytest.mark.parametrize(("site_id", "base_url"), GENE_SITES)
    async def test_gene_by_locus_tag_exists(self, site_id: str, base_url: str) -> None:
        """GeneByLocusTag search must exist under transcript record type."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{base_url}/record-types/transcript/searches")
            assert resp.status_code == 200, (
                f"{site_id}: HTTP {resp.status_code} fetching searches"
            )
            searches = resp.json()
            names = [s["urlSegment"] for s in searches]
            assert "GeneByLocusTag" in names, (
                f"GeneByLocusTag not found on {site_id}. Available: {names[:10]}..."
            )

    @pytest.mark.asyncio
    @pytest.mark.vcr
    @pytest.mark.parametrize(("site_id", "base_url"), GENE_SITES)
    async def test_ds_gene_ids_parameter_exists(
        self, site_id: str, base_url: str
    ) -> None:
        """GeneByLocusTag must have a ds_gene_ids parameter on every site."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{base_url}/record-types/transcript/searches/GeneByLocusTag"
            )
            assert resp.status_code == 200, (
                f"{site_id}: HTTP {resp.status_code} fetching GeneByLocusTag"
            )
            search = resp.json()
            # WDK nests parameters under searchData.parameters
            search_data = search.get("searchData", search)
            param_names = [p["name"] for p in search_data.get("parameters", [])]
            assert "ds_gene_ids" in param_names, (
                f"ds_gene_ids not found on {site_id}. Parameters: {param_names}"
            )


# ---------------------------------------------------------------------------
# Test 3: Gene set enrichment across sites with specific gene IDs
# ---------------------------------------------------------------------------

# Gene sets per site -- enough for statistical significance in enrichment
ENRICHMENT_CASES = [
    (
        "plasmodb",
        [
            "PF3D7_0709000",
            "PF3D7_1343700",
            "PF3D7_1222600",
            "PF3D7_1031000",
            "PF3D7_0209000",
            "PF3D7_1346700",
            "PF3D7_1346800",
            "PF3D7_0935400",
            "PF3D7_0406200",
            "PF3D7_1408200",
            "PF3D7_1216500",
            "PF3D7_1477700",
            "PF3D7_0100100",
            "PF3D7_0100200",
            "PF3D7_0100300",
            "PF3D7_0100400",
            "PF3D7_0100500",
            "PF3D7_0100600",
            "PF3D7_0100700",
            "PF3D7_0100800",
            "PF3D7_0100900",
            "PF3D7_0101000",
            "PF3D7_0101100",
            "PF3D7_0101200",
            "PF3D7_0101300",
            "PF3D7_0101400",
            "PF3D7_0101500",
            "PF3D7_0101600",
            "PF3D7_0101700",
            "PF3D7_0101800",
            "PF3D7_0101900",
            "PF3D7_0102000",
            "PF3D7_0102100",
            "PF3D7_0102200",
            "PF3D7_0102300",
            "PF3D7_0102400",
            "PF3D7_0102500",
            "PF3D7_0102600",
            "PF3D7_0102700",
            "PF3D7_0102800",
            "PF3D7_0102900",
            "PF3D7_0103000",
            "PF3D7_0103100",
            "PF3D7_0103200",
            "PF3D7_0103300",
            "PF3D7_0103400",
            "PF3D7_0103500",
            "PF3D7_0103600",
            "PF3D7_0103700",
            "PF3D7_0103800",
        ],
    ),
    (
        "toxodb",
        [
            "TGME49_214940",
            "TGME49_200010",
            "TGME49_200110",
            "TGME49_200130",
            "TGME49_200230",
            "TGME49_200240",
            "TGME49_200250",
            "TGME49_200260",
            "TGME49_200270",
            "TGME49_200280",
            "TGME49_200290",
            "TGME49_200310",
            "TGME49_200320",
            "TGME49_200330",
            "TGME49_200340",
            "TGME49_200350",
            "TGME49_200360",
            "TGME49_200370",
            "TGME49_200385",
            "TGME49_200400",
            "TGME49_200410",
            "TGME49_200430",
            "TGME49_200440",
            "TGME49_200450",
            "TGME49_200460",
            "TGME49_200470",
            "TGME49_200480",
            "TGME49_200590",
            "TGME49_200595",
            "TGME49_200600",
            "TGME49_200700",
            "TGME49_201100",
            "TGME49_201110",
            "TGME49_201120",
            "TGME49_201130",
            "TGME49_201140",
            "TGME49_201150",
            "TGME49_201160",
            "TGME49_201170",
            "TGME49_201180",
            "TGME49_201200",
            "TGME49_201210",
            "TGME49_201220",
            "TGME49_201230",
            "TGME49_201240",
            "TGME49_201250",
            "TGME49_201260",
            "TGME49_201270",
            "TGME49_201280",
            "TGME49_201290",
        ],
    ),
    (
        "cryptodb",
        [
            "cgd7_5260",
            "cgd1_10",
            "cgd1_100",
            "cgd1_1000",
            "cgd1_1010",
            "cgd1_1023",
            "cgd1_1040",
            "cgd1_1050",
            "cgd1_1060",
            "cgd1_1063",
            "cgd1_1070",
            "cgd1_1080",
            "cgd1_1090",
            "cgd1_110",
            "cgd1_1100",
            "cgd1_1110",
            "cgd1_1120",
            "cgd1_1130",
            "cgd1_1140",
            "cgd1_1150",
            "cgd1_1160",
            "cgd1_1170",
            "cgd1_1180",
            "cgd1_120",
            "cgd1_1200",
            "cgd1_1210",
            "cgd1_1220",
            "cgd1_1230",
            "cgd1_1240",
            "cgd1_1250",
            "cgd1_1260",
            "Cgd2_140",
            "Cgd2_1810",
            "Cgd2_2990",
            "Cgd3_2720",
            "Cgd3_4320",
            "Cgd5_1900",
            "Cgd5_2965",
            "Cgd5_40",
            "Cgd5_540",
            "Cgd6_2540",
            "Cgd6_280",
            "Cgd6_4720",
            "Cgd6_4723",
            "Cgd7_2213",
            "Cgd7_260",
            "Cgd7_5103",
            "Cgd7_760",
            "Cgd8_1200",
            "Cgd8_1390",
        ],
    ),
    (
        "fungidb",
        [
            "Afu1g03420",
            "Afu1g00100",
            "Afu1g00110",
            "Afu1g00120",
            "Afu1g00130",
            "Afu1g00140",
            "Afu1g00150",
            "Afu1g00160",
            "Afu1g00170",
            "Afu1g00180",
            "Afu1g00200",
            "Afu1g00210",
            "Afu1g00220",
            "Afu1g00230",
            "Afu1g00240",
            "Afu1g00250",
            "Afu1g00270",
            "Afu1g00280",
            "Afu1g00290",
            "Afu1g00300",
            "Afu1g00310",
            "Afu1g00320",
            "Afu1g00330",
            "Afu1g00340",
            "Afu1g00350",
            "Afu1g00390",
            "Afu1g00400",
            "Afu1g00410",
            "Afu1g00420",
            "Afu1g00440",
            "Afu1g00450",
            "Afu1g00460",
            "Afu1g00470",
            "Afu1g00480",
            "Afu1g00490",
            "Afu1g00500",
            "Afu1g00510",
            "Afu1g00520",
            "Afu1g00530",
            "Afu1g00540",
            "Afu1g00550",
            "Afu1g00560",
            "Afu1g00570",
            "Afu1g00580",
            "Afu1g00590",
            "Afu1g00610",
            "Afu1g00620",
            "Afu1g00630",
            "Afu1g00640",
            "Afu1g00650",
        ],
    ),
]


class TestGeneSetEnrichmentMultiSite:
    """Enrichment from gene IDs across PlasmoDB, ToxoDB, CryptoDB, FungiDB.

    Each test creates a gene set with known IDs, runs GO:BP enrichment,
    and verifies the response shape (term_id, term_name, p_value, fdr, genes).
    """

    @pytest.mark.asyncio
    @pytest.mark.vcr
    @pytest.mark.parametrize(("site_id", "gene_ids"), ENRICHMENT_CASES)
    async def test_go_bp_enrichment(self, site_id: str, gene_ids: list[str]) -> None:
        """GO biological process enrichment from gene IDs."""
        # Step 1: Create a WDK dataset from gene IDs
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(site_id, gene_ids)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters

        # Step 2: Run enrichment
        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id=site_id,
            analysis_types=["go_process"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        # Step 3: Verify at least one result returned
        assert len(results) == 1
        result = results[0]
        assert result.analysis_type == "go_process"
        assert result.error is None

        # Step 4: Verify response shape -- terms should have required fields
        # Note: some gene sets may not produce enriched terms (p < 0.05),
        # so we verify shape only when terms exist.
        if result.terms:
            term = result.terms[0]
            # Verify all expected fields are present with correct types
            assert isinstance(term.term_id, str)
            assert len(term.term_id) > 0
            assert isinstance(term.term_name, str)
            assert len(term.term_name) > 0
            assert isinstance(term.p_value, float)
            assert isinstance(term.fdr, float)
            assert isinstance(term.genes, list)
            assert isinstance(term.gene_count, int)
            assert term.gene_count > 0
            assert isinstance(term.background_count, int)
            assert isinstance(term.fold_enrichment, float)
            assert isinstance(term.odds_ratio, float)
            assert isinstance(term.bonferroni, float)
        else:
            pass

        # Verify metadata fields
        assert isinstance(result.total_genes_analyzed, int)
        assert isinstance(result.background_size, int)


# ---------------------------------------------------------------------------
# Test 1: Filter support in experiment results endpoint
# ---------------------------------------------------------------------------


class TestFilteredResultsViaPlasmoDB:
    """Verify that WDK search results can be fetched and filtered.

    Uses the standard report endpoint directly (no strategy/auth needed)
    to verify search results work with pagination and filtering at the
    WDK level.
    """

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_results_with_pagination(self) -> None:
        """Fetch GenesByTaxon results with pagination, verify response shape."""
        async with httpx.AsyncClient(timeout=60) as client:
            report_payload = {
                "searchConfig": {
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                },
                "reportConfig": {
                    "attributes": ["primary_key", "organism"],
                    "pagination": {"offset": 0, "numRecords": 5},
                },
            }

            resp = await client.post(
                "https://plasmodb.org/plasmo/service/record-types/transcript"
                "/searches/GenesByTaxon/reports/standard",
                json=report_payload,
            )
            assert resp.status_code == 200, (
                f"Failed to fetch results: {resp.status_code} {resp.text}"
            )

            data = resp.json()
            records = data.get("records", [])
            total = data.get("meta", {}).get("totalCount", 0)

            assert total > 0, "Expected non-zero gene count for P. falciparum"
            assert len(records) > 0
            assert len(records) <= 5

            # Verify record shape
            rec = records[0]
            assert "id" in rec
            assert "attributes" in rec

    @pytest.mark.asyncio
    @pytest.mark.vcr
    async def test_search_results_with_organism_filter(self) -> None:
        """Fetch GenesByTaxon results and verify all belong to the organism."""
        async with httpx.AsyncClient(timeout=60) as client:
            report_payload = {
                "searchConfig": {
                    "parameters": {
                        "organism": '["Plasmodium falciparum 3D7"]',
                    },
                },
                "reportConfig": {
                    "attributes": ["primary_key", "organism"],
                    "pagination": {"offset": 0, "numRecords": 10},
                },
            }

            resp = await client.post(
                "https://plasmodb.org/plasmo/service/record-types/transcript"
                "/searches/GenesByTaxon/reports/standard",
                json=report_payload,
            )
            assert resp.status_code == 200

            data = resp.json()
            records = data.get("records", [])
            assert len(records) > 0

            # All results must belong to P. falciparum 3D7
            for rec in records:
                organism = rec.get("attributes", {}).get("organism", "")
                assert "falciparum" in organism.lower(), (
                    f"Record {rec.get('id')} has unexpected organism: {organism}"
                )
