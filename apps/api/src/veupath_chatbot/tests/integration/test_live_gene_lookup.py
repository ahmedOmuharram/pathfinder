"""Live integration tests for gene lookup across multiple VEuPathDB databases.

Tests ``resolve_gene_ids()`` and ``fetch_wdk_text_genes()`` against REAL
WDK APIs -- no mocks, no fakes.  Every assertion is validated against
live PlasmoDB, ToxoDB, CryptoDB, FungiDB, TriTrypDB, and VectorBase.

Run::

    pytest src/veupath_chatbot/tests/integration/test_live_gene_lookup.py -v -s

Skip with::

    pytest -m "not live_wdk"
"""

from collections.abc import AsyncGenerator

import pytest

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.services.gene_lookup.wdk import (
    WDK_TEXT_FIELDS_BROAD,
    fetch_wdk_text_genes,
    resolve_gene_ids,
)

pytestmark = pytest.mark.live_wdk


# ---------------------------------------------------------------------------
# Fixture: close WDK HTTP clients after each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _close_wdk_clients() -> AsyncGenerator[None]:
    """Close shared WDK clients after each test to avoid leaked connections."""
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# Real gene IDs per database
# ---------------------------------------------------------------------------

PLASMO_GENES = [
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
]

# Large batches (50 genes each)

PLASMO_50 = [
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
    "PF3D7_0103900",
    "PF3D7_0104000",
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
]

TOXO_50 = [
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


# ---------------------------------------------------------------------------
# Organisms per database
# ---------------------------------------------------------------------------

PLASMO_ORGANISM = "Plasmodium falciparum 3D7"
TOXO_ORGANISM = "Toxoplasma gondii ME49"
CRYPTO_ORGANISM = "Cryptosporidium parvum Iowa II"
FUNGI_ORGANISM = "Aspergillus fumigatus Af293"
TRITRYP_ORGANISM = "Trypanosoma brucei brucei TREU927"
VECTOR_ORGANISM = "Anopheles gambiae PEST"


# ===================================================================
# 1. Resolve gene IDs across multiple databases
# ===================================================================


class TestResolveGeneIdsMultiDb:
    """Test ``resolve_gene_ids`` against every supported VEuPathDB site."""

    @pytest.mark.asyncio
    async def test_plasmodb_resolve_10_genes(self) -> None:
        """Resolve 10 P. falciparum genes from PlasmoDB."""
        result = await resolve_gene_ids("plasmodb", PLASMO_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)

    @pytest.mark.asyncio
    async def test_toxodb_resolve_10_genes(self) -> None:
        """Resolve 10 T. gondii genes from ToxoDB."""
        result = await resolve_gene_ids("toxodb", TOXO_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)

    @pytest.mark.asyncio
    async def test_cryptodb_resolve_10_genes(self) -> None:
        """Resolve 10 C. parvum genes from CryptoDB."""
        result = await resolve_gene_ids("cryptodb", CRYPTO_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)

    @pytest.mark.asyncio
    async def test_fungidb_resolve_10_genes(self) -> None:
        """Resolve 10 A. fumigatus genes from FungiDB."""
        result = await resolve_gene_ids("fungidb", FUNGI_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)

    @pytest.mark.asyncio
    async def test_tritrypdb_resolve_10_genes(self) -> None:
        """Resolve 10 T. brucei genes from TriTrypDB."""
        result = await resolve_gene_ids("tritrypdb", TRITRYP_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)

    @pytest.mark.asyncio
    async def test_vectorbase_resolve_10_genes(self) -> None:
        """Resolve 10 A. gambiae genes from VectorBase."""
        result = await resolve_gene_ids("vectorbase", VECTOR_GENES)

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) > 0
        assert isinstance(result["totalCount"], int)
        assert result["totalCount"] > 0
        for rec in records[:3]:
            assert isinstance(rec, dict)


# ===================================================================
# 2. Large gene set resolution
# ===================================================================


class TestResolveGeneIdsLargeSet:
    """Test ``resolve_gene_ids`` with large (50-gene) batches."""

    @pytest.mark.asyncio
    async def test_plasmodb_50_genes(self) -> None:
        """Resolve 50 P. falciparum genes from PlasmoDB."""
        result = await resolve_gene_ids("plasmodb", PLASMO_50)

        total = result.get("totalCount")
        records = result.get("records")
        assert isinstance(records, list)

        # Some IDs may not map to transcripts, but most should resolve
        assert isinstance(total, int)
        assert total >= 40, f"Expected >= 40 resolved, got {total}"
        assert len(records) >= 40

    @pytest.mark.asyncio
    async def test_toxodb_50_genes(self) -> None:
        """Resolve 50 T. gondii genes from ToxoDB."""
        result = await resolve_gene_ids("toxodb", TOXO_50)

        total = result.get("totalCount")
        records = result.get("records")
        assert isinstance(records, list)

        assert isinstance(total, int)
        assert total >= 40, f"Expected >= 40 resolved, got {total}"
        assert len(records) >= 40


# ===================================================================
# 3. Text search across multiple databases
# ===================================================================


class TestTextSearchMultiDb:
    """Test ``fetch_wdk_text_genes`` against every supported VEuPathDB site."""

    @pytest.mark.asyncio
    async def test_plasmodb_text_search(self) -> None:
        """Search for 'kinase' in P. falciparum via PlasmoDB."""
        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism=PLASMO_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass

    @pytest.mark.asyncio
    async def test_toxodb_text_search(self) -> None:
        """Search for 'kinase' in T. gondii via ToxoDB."""
        result = await fetch_wdk_text_genes(
            "toxodb",
            ["kinase*"],
            organism=TOXO_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass

    @pytest.mark.asyncio
    async def test_cryptodb_text_search(self) -> None:
        """Search for 'protease' in C. parvum via CryptoDB."""
        result = await fetch_wdk_text_genes(
            "cryptodb",
            ["protease*"],
            organism=CRYPTO_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass

    @pytest.mark.asyncio
    async def test_fungidb_text_search(self) -> None:
        """Search for 'kinase' in A. fumigatus via FungiDB."""
        result = await fetch_wdk_text_genes(
            "fungidb",
            ["kinase*"],
            organism=FUNGI_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass

    @pytest.mark.asyncio
    async def test_tritrypdb_text_search(self) -> None:
        """Search for 'kinase' in T. brucei via TriTrypDB."""
        result = await fetch_wdk_text_genes(
            "tritrypdb",
            ["kinase*"],
            organism=TRITRYP_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass

    @pytest.mark.asyncio
    async def test_vectorbase_text_search(self) -> None:
        """Search for 'kinase' in A. gambiae via VectorBase."""
        result = await fetch_wdk_text_genes(
            "vectorbase",
            ["kinase*"],
            organism=VECTOR_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass


# ===================================================================
# 4. Edge cases for resolve_gene_ids
# ===================================================================


class TestResolveEdgeCases:
    """Edge-case tests for ``resolve_gene_ids``."""

    @pytest.mark.asyncio
    async def test_empty_gene_list(self) -> None:
        """An empty gene list returns immediately with zero records."""
        result = await resolve_gene_ids("plasmodb", [])

        assert result == {"records": [], "totalCount": 0}

    @pytest.mark.asyncio
    async def test_single_gene_resolve(self) -> None:
        """Resolving exactly one gene returns exactly one record."""
        result = await resolve_gene_ids("plasmodb", ["PF3D7_1222600"])

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 1
        assert result["totalCount"] == 1
        rec = records[0]
        assert isinstance(rec, dict)
        assert rec.get("geneId") == "PF3D7_1222600"

    @pytest.mark.asyncio
    async def test_nonexistent_gene_id(self) -> None:
        """A completely fake gene ID should resolve to zero records (not error)."""
        result = await resolve_gene_ids("plasmodb", ["FAKE_GENE_12345"])

        records = result.get("records")
        assert isinstance(records, list)
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid(self) -> None:
        """Mix of real and fake IDs should return only the valid ones."""
        mixed = ["PF3D7_1222600", "FAKE_GENE_99999", "PF3D7_1031000", "BOGUS_XYZ"]
        result = await resolve_gene_ids("plasmodb", mixed)

        records = result.get("records")
        assert isinstance(records, list)
        # Should have exactly the 2 real genes
        assert len(records) == 2
        returned_ids = {str(r.get("geneId")) for r in records if isinstance(r, dict)}
        assert "PF3D7_1222600" in returned_ids
        assert "PF3D7_1031000" in returned_ids


# ===================================================================
# 5. Edge cases for fetch_wdk_text_genes
# ===================================================================


class TestTextSearchEdgeCases:
    """Edge-case tests for ``fetch_wdk_text_genes``."""

    @pytest.mark.asyncio
    async def test_no_organism_returns_empty(self) -> None:
        """Omitting organism returns an empty result (WDK requires it)."""
        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism=None,
        )

        assert result.total_count == 0
        assert len(result.records) == 0

    @pytest.mark.asyncio
    async def test_no_results_query(self) -> None:
        """A nonsense query should produce zero results."""
        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["xyzzyzzyzzy123"],
            organism=PLASMO_ORGANISM,
        )

        assert result.total_count == 0
        assert len(result.records) == 0

    @pytest.mark.asyncio
    async def test_broad_text_fields(self) -> None:
        """Searching with broad text fields (product, name, GO, etc.)."""
        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism=PLASMO_ORGANISM,
            text_fields=WDK_TEXT_FIELDS_BROAD,
        )

        assert result.total_count > 0
        assert len(result.records) > 0
        for _rec in result.records[:3]:
            pass
