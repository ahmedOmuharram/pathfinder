"""Tests for services.gene_lookup.site_search -- site-search parsing and fetching."""

from typing import cast
from unittest.mock import AsyncMock, patch

from veupath_chatbot.services.gene_lookup.site_search import (
    SITE_SEARCH_FETCH_LIMIT,
    fetch_site_search_genes,
    parse_site_search_docs,
)

# ---------------------------------------------------------------------------
# parse_site_search_docs
# ---------------------------------------------------------------------------


class TestParseSiteSearchDocs:
    """Tests for converting raw site-search documents into gene dicts."""

    def _make_doc(
        self,
        gene_id: str = "PF3D7_0100100",
        *,
        organism: str = "Plasmodium falciparum 3D7",
        product: str = "erythrocyte membrane protein",
        gene_name: str = "PfEMP1",
        gene_type: str = "protein coding",
        hyperlink_name: str = "",
        found_in_fields: dict[str, list[str]] | None = None,
        primary_key: list[str] | None = None,
    ) -> dict[str, object]:
        doc: dict[str, object] = {
            "wdkPrimaryKeyString": gene_id,
            "summaryFieldData": {
                "TEXT__gene_organism_full": organism,
                "TEXT__gene_product": product,
                "TEXT__gene_name": gene_name,
                "TEXT__gene_type": gene_type,
            },
        }
        if hyperlink_name:
            doc["hyperlinkName"] = hyperlink_name
        if found_in_fields is not None:
            doc["foundInFields"] = found_in_fields
        if primary_key is not None:
            doc["primaryKey"] = primary_key
        return doc

    def test_basic_parsing(self) -> None:
        docs = [self._make_doc()]
        results = parse_site_search_docs(cast("list[object]", docs))
        assert len(results) == 1
        r = results[0]
        assert r["geneId"] == "PF3D7_0100100"
        assert r["organism"] == "Plasmodium falciparum 3D7"
        assert r["product"] == "erythrocyte membrane protein"
        assert r["geneName"] == "PfEMP1"
        assert r["geneType"] == "protein coding"

    def test_html_tags_stripped_from_fields(self) -> None:
        doc = self._make_doc(
            gene_id="<em>PF3D7_0100100</em>",
            product="<em>erythrocyte</em> membrane protein",
            gene_name="<b>PfEMP1</b>",
        )
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["geneId"] == "PF3D7_0100100"
        assert results[0]["product"] == "erythrocyte membrane protein"
        assert results[0]["geneName"] == "PfEMP1"

    def test_fallback_to_primary_key_list(self) -> None:
        doc = self._make_doc()
        doc["wdkPrimaryKeyString"] = ""
        doc["primaryKey"] = ["PF3D7_0200200"]
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["geneId"] == "PF3D7_0200200"

    def test_skip_doc_without_gene_id(self) -> None:
        doc = self._make_doc(gene_id="")
        doc["primaryKey"] = []
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results == []

    def test_non_dict_docs_skipped(self) -> None:
        results = parse_site_search_docs(cast("list[object]", ["not a dict", 42, None]))
        assert results == []

    def test_missing_summary_field_data(self) -> None:
        doc: dict[str, object] = {"wdkPrimaryKeyString": "PF3D7_0100100"}
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert len(results) == 1
        assert results[0]["geneId"] == "PF3D7_0100100"
        assert results[0]["organism"] == ""
        assert results[0]["product"] == ""

    def test_hyperlink_name_used_as_display_name(self) -> None:
        doc = self._make_doc(hyperlink_name="My Gene Display Name")
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["displayName"] == "My Gene Display Name"

    def test_display_name_fallback_chain(self) -> None:
        # No hyperlinkName, no gene_name => falls back to product
        doc = self._make_doc(gene_name="", hyperlink_name="")
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["displayName"] == "erythrocyte membrane protein"

    def test_display_name_fallback_to_gene_name(self) -> None:
        doc = self._make_doc(hyperlink_name="", gene_name="MyGene")
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["displayName"] == "MyGene"

    def test_found_in_fields_parsed(self) -> None:
        doc = self._make_doc(
            found_in_fields={
                "TEXT__gene_product": ["match1"],
                "MULTITEXT__gene_Notes": ["note1"],
            }
        )
        results = parse_site_search_docs(cast("list[object]", [doc]))
        matched = results[0]["matchedFields"]
        assert isinstance(matched, list)
        assert "gene_product" in matched
        assert "gene_Notes" in matched

    def test_found_in_fields_skips_empty_values(self) -> None:
        doc = self._make_doc(
            found_in_fields={
                "TEXT__gene_product": [],  # empty => skip
                "TEXT__gene_name": ["match"],
            }
        )
        results = parse_site_search_docs(cast("list[object]", [doc]))
        matched = results[0]["matchedFields"]
        assert isinstance(matched, list)
        assert "gene_product" not in matched
        assert "gene_name" in matched

    def test_organism_fallback_to_doc_level(self) -> None:
        """When summary organism is empty, fall back to doc-level organism."""
        doc = self._make_doc(organism="")
        doc["organism"] = "Toxoplasma gondii ME49"
        results = parse_site_search_docs(cast("list[object]", [doc]))
        assert results[0]["organism"] == "Toxoplasma gondii ME49"

    def test_multiple_docs(self) -> None:
        docs = [
            self._make_doc(gene_id="GENE_A"),
            self._make_doc(gene_id="GENE_B"),
            self._make_doc(gene_id="GENE_C"),
        ]
        results = parse_site_search_docs(cast("list[object]", docs))
        assert len(results) == 3
        assert [r["geneId"] for r in results] == ["GENE_A", "GENE_B", "GENE_C"]


# ---------------------------------------------------------------------------
# fetch_site_search_genes
# ---------------------------------------------------------------------------


class TestFetchSiteSearchGenes:
    """Tests for the async site-search wrapper."""

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_basic_fetch(self, mock_query: AsyncMock) -> None:
        mock_query.return_value = {
            "searchResults": {
                "totalCount": 1,
                "documents": [
                    {
                        "wdkPrimaryKeyString": "PF3D7_0100100",
                        "summaryFieldData": {
                            "TEXT__gene_organism_full": "Plasmodium falciparum 3D7",
                            "TEXT__gene_product": "some product",
                            "TEXT__gene_name": "SomeName",
                            "TEXT__gene_type": "protein coding",
                        },
                    }
                ],
            },
            "organismCounts": {
                "Plasmodium falciparum 3D7": 100,
                "Plasmodium vivax P01": 10,
            },
        }

        results, organisms, total = await fetch_site_search_genes("plasmodb", "kinase")
        assert len(results) == 1
        assert results[0]["geneId"] == "PF3D7_0100100"
        assert total == 1
        assert "Plasmodium falciparum 3D7" in organisms
        assert "Plasmodium vivax P01" in organisms

        mock_query.assert_called_once_with(
            "plasmodb",
            search_text="kinase",
            document_type="gene",
            organisms=None,
            limit=SITE_SEARCH_FETCH_LIMIT,
            offset=0,
        )

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_with_organisms_filter(self, mock_query: AsyncMock) -> None:
        mock_query.return_value = {
            "searchResults": {"totalCount": 0, "documents": []},
            "organismCounts": {},
        }

        await fetch_site_search_genes(
            "plasmodb",
            "kinase",
            organisms=["Plasmodium falciparum 3D7"],
            limit=10,
        )

        mock_query.assert_called_once_with(
            "plasmodb",
            search_text="kinase",
            document_type="gene",
            organisms=["Plasmodium falciparum 3D7"],
            limit=10,
            offset=0,
        )

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_empty_response(self, mock_query: AsyncMock) -> None:
        mock_query.return_value = {}

        results, organisms, total = await fetch_site_search_genes("plasmodb", "zzz")
        assert results == []
        assert organisms == []
        assert total == 0

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_non_dict_response(self, mock_query: AsyncMock) -> None:
        mock_query.return_value = "not a dict"

        results, organisms, _total = await fetch_site_search_genes("plasmodb", "zzz")
        assert results == []
        assert organisms == []

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_total_count_fallback_to_len(self, mock_query: AsyncMock) -> None:
        """When totalCount is not an int, fall back to len(results)."""
        mock_query.return_value = {
            "searchResults": {
                "totalCount": "not an int",
                "documents": [
                    {
                        "wdkPrimaryKeyString": "GENE_A",
                        "summaryFieldData": {},
                    },
                ],
            },
        }

        results, _, total = await fetch_site_search_genes("plasmodb", "kinase")
        assert len(results) == 1
        assert total == 1

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.query_site_search",
        new_callable=AsyncMock,
    )
    async def test_organism_counts_sorted(self, mock_query: AsyncMock) -> None:
        mock_query.return_value = {
            "searchResults": {"totalCount": 0, "documents": []},
            "organismCounts": {
                "Zzzorganism": 5,
                "Aaaorganism": 10,
                "Mmmorganism": 3,
            },
        }

        _, organisms, _ = await fetch_site_search_genes("plasmodb", "kinase")
        assert organisms == ["Aaaorganism", "Mmmorganism", "Zzzorganism"]


class TestSiteSearchFetchLimit:
    def test_limit_is_50(self) -> None:
        assert SITE_SEARCH_FETCH_LIMIT == 50
