"""Tests for services.gene_lookup.enrich -- sparse gene result enrichment.

Mocks: resolve_gene_ids is mocked. Tests validate enrichment merge logic
(field merging, display name generation, error fallback) with controlled data,
not WDK integration.
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.gene_lookup.enrich import enrich_sparse_gene_results
from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.wdk import GeneResolveResult


def _gene(
    gene_id: str,
    *,
    organism: str = "",
    product: str = "",
    gene_name: str = "",
    gene_type: str = "",
    location: str = "",
) -> GeneResult:
    return GeneResult(
        gene_id=gene_id,
        organism=organism,
        product=product,
        gene_name=gene_name,
        gene_type=gene_type,
        location=location,
    )


class TestEnrichSparseGeneResults:
    """Tests for the WDK-based enrichment of sparse site-search results."""

    async def test_no_enrichment_needed(self) -> None:
        """If all results already have organism and product, skip WDK call."""
        results = [
            _gene("G1", organism="Pf", product="kinase"),
            _gene("G2", organism="Tg", product="protease"),
        ]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert len(enriched) == 2
        # Original data untouched
        assert enriched[0].gene_id == "G1"
        assert enriched[1].gene_id == "G2"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_missing_organism(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="Plasmodium falciparum 3D7",
                    product="erythrocyte membrane protein",
                    gene_name="EMP1",
                    gene_type="protein coding",
                    location="chr1:100-200(+)",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1", product="erythrocyte membrane protein")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].organism == "Plasmodium falciparum 3D7"
        # product was already present, should not be overwritten
        assert enriched[0].product == "erythrocyte membrane protein"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_missing_product(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="Pf",
                    product="some product",
                    gene_name="SomeName",
                    gene_type="protein coding",
                    location="",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1", organism="Pf")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].product == "some product"
        # organism was already present
        assert enriched[0].organism == "Pf"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_gene_name_type_location(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="Pf",
                    product="kinase",
                    gene_name="MyKinase",
                    gene_type="protein coding",
                    location="chr3:500-600(-)",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1")]  # Missing everything
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].gene_name == "MyKinase"
        assert enriched[0].gene_type == "protein coding"
        assert enriched[0].location == "chr3:500-600(-)"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_does_not_overwrite_existing_fields(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="NEW_ORG",
                    product="NEW_PROD",
                    gene_name="NEW_NAME",
                    gene_type="NEW_TYPE",
                    location="NEW_LOC",
                ),
            ],
            total_count=1,
        )
        # All fields present, so none should need enrichment... but organism+product present
        # means gene won't be in ids_to_enrich. Let's test with missing product:
        results = [_gene("G1", organism="OLD_ORG", gene_name="OLD_NAME")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].organism == "OLD_ORG"  # not overwritten
        assert enriched[0].gene_name == "OLD_NAME"  # not overwritten
        assert enriched[0].product == "NEW_PROD"  # filled in

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_display_name_generated(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="Pf",
                    product="kinase product",
                    gene_name="",
                    gene_type="",
                    location="",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        # displayName should be set to product since geneName is empty
        assert enriched[0].display_name == "kinase product"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_display_name_prefers_gene_name(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="G1",
                    organism="Pf",
                    product="kinase product",
                    gene_name="MyKinase",
                    gene_type="",
                    location="",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        # geneName from meta fills in via _merge_meta
        assert enriched[0].display_name in ("MyKinase", "kinase product", "G1")

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_wdk_error_returns_original_results(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.side_effect = WDKError(detail="WDK down")
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        # Should return original results unchanged
        assert enriched == results

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_resolved_error_returns_original(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[], total_count=0, error="Something went wrong"
        )
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched == results

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_resolved_no_records_returns_original(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = GeneResolveResult(records=[], total_count=0)
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched == results

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_limit_applied_to_output(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(gene_id="G1", organism="Pf", product="prod1"),
                GeneResult(gene_id="G2", organism="Pf", product="prod2"),
            ],
            total_count=2,
        )
        results = [
            _gene("G1"),
            _gene("G2"),
            _gene("G3", organism="Pf", product="prod3"),
        ]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 2)
        assert len(enriched) == 2

    async def test_empty_results_passed_through(self) -> None:
        """Empty results list should pass through without WDK calls."""
        enriched = await enrich_sparse_gene_results("plasmodb", [], 10)
        assert enriched == []

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_gene_id_whitespace_stripped_in_lookup(
        self, mock_resolve: AsyncMock
    ) -> None:
        """Gene ID matching should strip whitespace."""
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(
                    gene_id="  G1  ",
                    organism="Pf",
                    product="enriched product",
                ),
            ],
            total_count=1,
        )
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].product == "enriched product"
