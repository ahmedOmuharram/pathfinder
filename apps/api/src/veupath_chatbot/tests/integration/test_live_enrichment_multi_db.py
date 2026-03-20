"""Live integration tests for enrichment across multiple VEuPathDB databases.

Tests _build_enrichment_params_from_gene_ids, EnrichmentService.run(),
and EnrichmentService.run_batch() against REAL WDK APIs with REAL gene IDs
from six VEuPathDB databases: PlasmoDB, ToxoDB, CryptoDB, FungiDB,
TriTrypDB, and VectorBase.

NO MOCKS. All calls hit live WDK endpoints.

Requires network access to VEuPathDB sites. Run with:

    pytest src/veupath_chatbot/tests/integration/test_live_enrichment_multi_db.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator

import pytest

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.gene_sets.operations import (
    _build_enrichment_params_from_gene_ids,
)
from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

pytestmark = pytest.mark.live_wdk

# ---------------------------------------------------------------------------
# Real gene IDs — 50 per database for statistical power
# ---------------------------------------------------------------------------

PLASMO_GENES = [
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
    "PF3D7_0103100",
    "PF3D7_0103200",
    "PF3D7_0103300",
    "PF3D7_0103400",
    "PF3D7_0103500",
    "PF3D7_0103600",
    "PF3D7_0103700",
    "PF3D7_0103800",
    "PF3D7_0103900",
    "PF3D7_0104000",
]

TOXO_GENES = [
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
    "TGME49_201300",
]

CRYPTO_GENES = [
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
    "cgd1_1190",
]

FUNGI_GENES = [
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
    "Afu1g00660",
]

TRITRYP_GENES = [
    "Tb05.5K5.10",
    "Tb05.5K5.100",
    "Tb05.5K5.110",
    "Tb05.5K5.120",
    "Tb05.5K5.130",
    "Tb05.5K5.140",
    "Tb05.5K5.150",
    "Tb05.5K5.160",
    "Tb05.5K5.170",
    "Tb05.5K5.180",
    "Tb05.5K5.190",
    "Tb05.5K5.20",
    "Tb05.5K5.200",
    "Tb05.5K5.210",
    "Tb05.5K5.220",
    "Tb05.5K5.230",
    "Tb05.5K5.240",
    "Tb05.5K5.250",
    "Tb05.5K5.260",
    "Tb05.5K5.270",
    "Tb05.5K5.280",
    "Tb05.5K5.290",
    "Tb05.5K5.30",
    "Tb05.5K5.300",
    "Tb05.5K5.310",
    "Tb05.5K5.320",
    "Tb05.5K5.330",
    "Tb05.5K5.340",
    "Tb05.5K5.350",
    "Tb05.5K5.360",
    "Tb05.5K5.370",
    "Tb05.5K5.380",
    "Tb05.5K5.390",
    "Tb05.5K5.40",
    "Tb05.5K5.400",
    "Tb05.5K5.410",
    "Tb05.5K5.420",
    "Tb05.5K5.430",
    "Tb05.5K5.440",
    "Tb05.5K5.450",
    "Tb05.5K5.460",
    "Tb05.5K5.470",
    "Tb05.5K5.480",
    "Tb05.5K5.490",
    "Tb05.5K5.50",
    "Tb05.5K5.500",
    "Tb05.5K5.510",
    "Tb04.24M18.150",
    "Tb04.3I12.100",
    "Tb05.30F7.410",
]

VECTOR_GENES = [
    "AGAP000002",
    "AGAP000005",
    "AGAP000007",
    "AGAP000008",
    "AGAP000009",
    "AGAP000010",
    "AGAP000011",
    "AGAP000012",
    "AGAP000013",
    "AGAP000014",
    "AGAP000015",
    "AGAP000016",
    "AGAP000017",
    "AGAP000018",
    "AGAP000019",
    "AGAP000021",
    "AGAP000022",
    "AGAP000023",
    "AGAP000025",
    "AGAP000028",
    "AGAP000029",
    "AGAP000032",
    "AGAP000033",
    "AGAP000035",
    "AGAP000037",
    "AGAP000038",
    "AGAP000039",
    "AGAP000040",
    "AGAP000041",
    "AGAP000042",
    "AGAP000043",
    "AGAP000044",
    "AGAP000045",
    "AGAP000046",
    "AGAP000047",
    "AGAP000048",
    "AGAP000049",
    "AGAP000050",
    "AGAP000051",
    "AGAP000052",
    "AGAP000053",
    "AGAP000054",
    "AGAP000055",
    "AGAP000056",
    "AGAP000057",
    "AGAP000058",
    "AGAP000059",
    "AGAP000060",
    "AGAP000061",
    "AGAP000062",
]

# Additional PlasmoDB genes for the large gene set test (100 total)
PLASMO_EXTRA_GENES = [
    "PF3D7_0104100",
    "PF3D7_0104200",
    "PF3D7_0104300",
    "PF3D7_0104400",
    "PF3D7_0104500",
    "PF3D7_0104600",
    "PF3D7_0104700",
    "PF3D7_0104800",
    "PF3D7_0104900",
    "PF3D7_0105000",
    "PF3D7_0200100",
    "PF3D7_0200200",
    "PF3D7_0200300",
    "PF3D7_0200400",
    "PF3D7_0200500",
    "PF3D7_0200600",
    "PF3D7_0200700",
    "PF3D7_0200800",
    "PF3D7_0200900",
    "PF3D7_0201000",
    "PF3D7_0201100",
    "PF3D7_0201200",
    "PF3D7_0201300",
    "PF3D7_0201400",
    "PF3D7_0201500",
    "PF3D7_0201600",
    "PF3D7_0201700",
    "PF3D7_0201800",
    "PF3D7_0201900",
    "PF3D7_0202000",
    "PF3D7_0202100",
    "PF3D7_0202200",
    "PF3D7_0202300",
    "PF3D7_0202400",
    "PF3D7_0202500",
    "PF3D7_0202600",
    "PF3D7_0202700",
    "PF3D7_0202800",
    "PF3D7_0202900",
    "PF3D7_0203000",
    "PF3D7_0203100",
    "PF3D7_0203200",
    "PF3D7_0203300",
    "PF3D7_0203400",
    "PF3D7_0203500",
    "PF3D7_0203600",
    "PF3D7_0203700",
    "PF3D7_0203800",
    "PF3D7_0203900",
    "PF3D7_0204000",
]


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
# 1. Dataset creation from gene IDs — all six databases
# ---------------------------------------------------------------------------


class TestBuildEnrichmentParamsMultiDb:
    """Test _build_enrichment_params_from_gene_ids against each VEuPathDB site.

    Each test uploads 50 real gene IDs to the target site, creating a
    WDK dataset, and verifies the returned search_name, record_type,
    and parameter structure are correct for enrichment.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_dataset_creation(self) -> None:
        """Upload 50 P. falciparum genes to PlasmoDB and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("plasmodb", PLASMO_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.asyncio
    async def test_toxodb_dataset_creation(self) -> None:
        """Upload 50 T. gondii genes to ToxoDB and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("toxodb", TOXO_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.asyncio
    async def test_cryptodb_dataset_creation(self) -> None:
        """Upload 50 C. parvum genes to CryptoDB and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("cryptodb", CRYPTO_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.asyncio
    async def test_fungidb_dataset_creation(self) -> None:
        """Upload 50 A. fumigatus genes to FungiDB and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("fungidb", FUNGI_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.asyncio
    async def test_tritrypdb_dataset_creation(self) -> None:
        """Upload 50 T. brucei genes to TriTrypDB and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("tritrypdb", TRITRYP_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0

    @pytest.mark.asyncio
    async def test_vectorbase_dataset_creation(self) -> None:
        """Upload 50 A. gambiae genes to VectorBase and verify params."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("vectorbase", VECTOR_GENES)

        assert search_name == "GeneByLocusTag"
        assert record_type == "transcript"
        assert "ds_gene_ids" in parameters
        ds_id = parameters["ds_gene_ids"]
        assert isinstance(ds_id, str)
        assert len(ds_id) > 0


# ---------------------------------------------------------------------------
# 2. GO enrichment via run_batch — one type per database
# ---------------------------------------------------------------------------


class TestEnrichmentMultiDb:
    """Test EnrichmentService.run_batch() with GO process enrichment per DB.

    Each test builds enrichment params from 50 real gene IDs, then runs
    a single GO process enrichment via run_batch(). Validates the result
    structure: one result, correct analysis_type, no error.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_go_enrichment(self) -> None:
        """GO process enrichment on 50 P. falciparum genes via PlasmoDB."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("plasmodb", PLASMO_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="plasmodb",
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

    @pytest.mark.asyncio
    async def test_toxodb_go_enrichment(self) -> None:
        """GO process enrichment on 50 T. gondii genes via ToxoDB."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("toxodb", TOXO_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="toxodb",
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

    @pytest.mark.asyncio
    async def test_cryptodb_go_enrichment(self) -> None:
        """GO process enrichment on 50 C. parvum genes via CryptoDB."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("cryptodb", CRYPTO_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="cryptodb",
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

    @pytest.mark.asyncio
    async def test_fungidb_go_enrichment(self) -> None:
        """GO process enrichment on 50 A. fumigatus genes via FungiDB."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("fungidb", FUNGI_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="fungidb",
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

    @pytest.mark.asyncio
    async def test_tritrypdb_go_enrichment(self) -> None:
        """GO process enrichment on 50 T. brucei genes via TriTrypDB."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("tritrypdb", TRITRYP_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="tritrypdb",
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

    @pytest.mark.asyncio
    async def test_vectorbase_go_enrichment(self) -> None:
        """GO process enrichment on 50 A. gambiae genes via VectorBase."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("vectorbase", VECTOR_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="vectorbase",
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


# ---------------------------------------------------------------------------
# 3. Multiple enrichment types concurrently per database
# ---------------------------------------------------------------------------


class TestMultiTypeEnrichment:
    """Test run_batch() with multiple enrichment types in a single call.

    Verifies concurrent execution of GO process, GO function, and
    GO component enrichment types on a shared temporary WDK step.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_multi_type(self) -> None:
        """GO process + function + component on 50 PlasmoDB genes."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("plasmodb", PLASMO_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="plasmodb",
            analysis_types=["go_process", "go_function", "go_component"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for _r in results:
            pass

        assert len(results) == 3
        result_types = {r.analysis_type for r in results}
        assert result_types == {"go_process", "go_function", "go_component"}

    @pytest.mark.asyncio
    async def test_toxodb_multi_type(self) -> None:
        """GO process + function on 50 ToxoDB genes."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("toxodb", TOXO_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="toxodb",
            analysis_types=["go_process", "go_function"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for _r in results:
            pass

        assert len(results) == 2
        result_types = {r.analysis_type for r in results}
        assert result_types == {"go_process", "go_function"}

    @pytest.mark.asyncio
    async def test_fungidb_multi_type(self) -> None:
        """GO process + function + component on 50 FungiDB genes."""
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("fungidb", FUNGI_GENES)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="fungidb",
            analysis_types=["go_process", "go_function", "go_component"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for _r in results:
            pass

        assert len(results) == 3
        result_types = {r.analysis_type for r in results}
        assert result_types == {"go_process", "go_function", "go_component"}


# ---------------------------------------------------------------------------
# 4. Large gene set enrichment
# ---------------------------------------------------------------------------


class TestLargeGeneSetEnrichment:
    """Test enrichment with larger-than-typical gene sets.

    Verifies that the WDK dataset creation and enrichment pipeline
    handles 100 gene IDs without issues.
    """

    @pytest.mark.asyncio
    async def test_plasmodb_100_genes(self) -> None:
        """Enrichment with 100 P. falciparum genes (50 base + 50 extra)."""
        large_gene_set = PLASMO_GENES + PLASMO_EXTRA_GENES
        assert len(large_gene_set) == 100

        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("plasmodb", large_gene_set)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="plasmodb",
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


# ---------------------------------------------------------------------------
# 5. Edge cases
# ---------------------------------------------------------------------------


class TestEnrichmentEdgeCases:
    """Test edge cases for enrichment: single gene, missing params, etc."""

    @pytest.mark.asyncio
    async def test_single_gene_enrichment(self) -> None:
        """Enrichment with a single gene should still work (may return empty terms)."""
        single_gene = [PLASMO_GENES[0]]

        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids("plasmodb", single_gene)

        svc = EnrichmentService()
        results, _errors = await svc.run_batch(
            site_id="plasmodb",
            analysis_types=["go_process"],
            search_name=search_name,
            record_type=record_type,
            parameters=parameters,
        )

        for _r in results:
            pass

        # Should return one result — may have zero terms but should not error
        assert len(results) == 1
        result = results[0]
        assert result.analysis_type == "go_process"

    @pytest.mark.asyncio
    async def test_empty_search_name_raises(self) -> None:
        """Empty search_name with no step_id should raise ValueError."""
        svc = EnrichmentService()
        with pytest.raises(ValueError, match="step_id or search_name"):
            await svc.run_batch(
                site_id="plasmodb",
                analysis_types=["go_process"],
                step_id=None,
                search_name="",
                parameters={},
            )

    @pytest.mark.asyncio
    async def test_missing_params_raises(self) -> None:
        """No parameters with no step_id should raise ValueError."""
        svc = EnrichmentService()
        with pytest.raises(ValueError, match="step_id or search_name"):
            await svc.run_batch(
                site_id="plasmodb",
                analysis_types=["go_process"],
                step_id=None,
                search_name=None,
                parameters=None,
            )
