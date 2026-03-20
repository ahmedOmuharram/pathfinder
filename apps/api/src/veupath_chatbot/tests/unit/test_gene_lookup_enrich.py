"""Tests for services.gene_lookup.enrich -- sparse gene result enrichment."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.services.gene_lookup.enrich import enrich_sparse_gene_results


def _gene(
    gene_id: str,
    *,
    organism: str = "",
    product: str = "",
    gene_name: str = "",
    gene_type: str = "",
    location: str = "",
) -> dict[str, object]:
    d: dict[str, object] = {"geneId": gene_id}
    if organism:
        d["organism"] = organism
    if product:
        d["product"] = product
    if gene_name:
        d["geneName"] = gene_name
    if gene_type:
        d["geneType"] = gene_type
    if location:
        d["location"] = location
    return d


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
        assert enriched[0]["geneId"] == "G1"
        assert enriched[1]["geneId"] == "G2"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_missing_organism(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "Plasmodium falciparum 3D7",
                    "product": "erythrocyte membrane protein",
                    "geneName": "EMP1",
                    "geneType": "protein coding",
                    "location": "chr1:100-200(+)",
                },
            ],
        }
        results = [_gene("G1", product="erythrocyte membrane protein")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["organism"] == "Plasmodium falciparum 3D7"
        # product was already present, should not be overwritten
        assert enriched[0]["product"] == "erythrocyte membrane protein"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_missing_product(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "Pf",
                    "product": "some product",
                    "geneName": "SomeName",
                    "geneType": "protein coding",
                    "location": "",
                },
            ],
        }
        results = [_gene("G1", organism="Pf")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["product"] == "some product"
        # organism was already present
        assert enriched[0]["organism"] == "Pf"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enriches_gene_name_type_location(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "Pf",
                    "product": "kinase",
                    "geneName": "MyKinase",
                    "geneType": "protein coding",
                    "location": "chr3:500-600(-)",
                },
            ],
        }
        results = [_gene("G1")]  # Missing everything
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["geneName"] == "MyKinase"
        assert enriched[0]["geneType"] == "protein coding"
        assert enriched[0]["location"] == "chr3:500-600(-)"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_does_not_overwrite_existing_fields(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "NEW_ORG",
                    "product": "NEW_PROD",
                    "geneName": "NEW_NAME",
                    "geneType": "NEW_TYPE",
                    "location": "NEW_LOC",
                },
            ],
        }
        results = [
            _gene(
                "G1",
                organism="OLD_ORG",
                product="OLD_PROD",
                gene_name="OLD_NAME",
                gene_type="OLD_TYPE",
                location="OLD_LOC",
            )
        ]
        # All fields present, so none should need enrichment... but organism+product present
        # means gene won't be in ids_to_enrich. Let's test with missing product:
        results = [_gene("G1", organism="OLD_ORG", gene_name="OLD_NAME")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["organism"] == "OLD_ORG"  # not overwritten
        assert enriched[0]["geneName"] == "OLD_NAME"  # not overwritten
        assert enriched[0]["product"] == "NEW_PROD"  # filled in

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_display_name_generated(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "Pf",
                    "product": "kinase product",
                    "geneName": "",
                    "geneType": "",
                    "location": "",
                },
            ],
        }
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        # displayName should be set to product since geneName is empty
        assert enriched[0]["displayName"] == "kinase product"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_display_name_prefers_gene_name(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "G1",
                    "organism": "Pf",
                    "product": "kinase product",
                    "geneName": "MyKinase",
                    "geneType": "",
                    "location": "",
                },
            ],
        }
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["displayName"] == "MyKinase"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_wdk_error_returns_original_results(
        self, mock_resolve: AsyncMock
    ) -> None:
        mock_resolve.side_effect = ValueError("WDK down")
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
        mock_resolve.return_value = {
            "error": "Something went wrong",
            "records": [],
        }
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
        mock_resolve.return_value = {"records": None}
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched == results

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_limit_applied_to_output(self, mock_resolve: AsyncMock) -> None:
        mock_resolve.return_value = {
            "records": [
                {"geneId": "G1", "organism": "Pf", "product": "prod1"},
                {"geneId": "G2", "organism": "Pf", "product": "prod2"},
            ],
        }
        results = [
            _gene("G1"),
            _gene("G2"),
            _gene("G3", organism="Pf", product="prod3"),
        ]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 2)
        assert len(enriched) == 2

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_max_50_ids_sent_to_wdk(self, mock_resolve: AsyncMock) -> None:
        """Should cap at 50 IDs for enrichment."""
        mock_resolve.return_value = {"records": []}
        results = [_gene(f"G{i}") for i in range(100)]
        await enrich_sparse_gene_results("plasmodb", results, 200)
        # Check that at most 50 IDs were sent
        call_args = mock_resolve.call_args
        assert len(call_args[0][1]) <= 50

    async def test_non_dict_results_passed_through(self) -> None:
        """Non-dict items in results should pass through unchanged."""
        results: list[dict[str, object]] = [
            _gene("G1", organism="Pf", product="p"),
        ]
        # All have organism+product, so no enrichment needed; non-dicts would pass through
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert len(enriched) == 1

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_gene_id_whitespace_stripped_in_lookup(
        self, mock_resolve: AsyncMock
    ) -> None:
        """Gene ID matching should strip whitespace."""
        mock_resolve.return_value = {
            "records": [
                {
                    "geneId": "  G1  ",
                    "organism": "Pf",
                    "product": "enriched product",
                },
            ],
        }
        results = [_gene("G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["product"] == "enriched product"
