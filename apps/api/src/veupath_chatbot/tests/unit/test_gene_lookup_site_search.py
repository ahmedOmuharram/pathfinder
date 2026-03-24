"""Tests for services.gene_lookup.site_search -- site-search parsing and fetching."""

from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.integrations.veupathdb.site_search_client import (
    SiteSearchDocument,
    SiteSearchResponse,
    SiteSearchResults,
)
from veupath_chatbot.services.gene_lookup.site_search import (
    SITE_SEARCH_FETCH_LIMIT,
    fetch_site_search_genes,
    parse_site_search_docs,
)

# ---------------------------------------------------------------------------
# parse_site_search_docs
# ---------------------------------------------------------------------------


def _make_doc(
    gene_id: str = "PF3D7_0100100",
    *,
    organism: str = "Plasmodium falciparum 3D7",
    product: str = "erythrocyte membrane protein",
    gene_name: str = "PfEMP1",
    gene_type: str = "protein coding",
    extra_fields: dict[str, object] | None = None,
) -> SiteSearchDocument:
    summary: dict[str, str | list[str]] = {
        "TEXT__gene_organism_full": organism,
        "TEXT__gene_product": product,
        "TEXT__gene_name": gene_name,
        "TEXT__gene_type": gene_type,
    }
    kwargs: dict[str, object] = {
        "wdk_primary_key_string": gene_id,
        "summary_field_data": summary,
    }
    if extra_fields:
        kwargs.update(extra_fields)
    return SiteSearchDocument(**kwargs)


class TestParseSiteSearchDocs:
    """Tests for converting typed site-search documents into GeneResult objects."""

    def test_basic_parsing(self) -> None:
        docs = [_make_doc()]
        results = parse_site_search_docs(docs)
        assert len(results) == 1
        r = results[0]
        assert r.gene_id == "PF3D7_0100100"
        assert r.organism == "Plasmodium falciparum 3D7"
        assert r.product == "erythrocyte membrane protein"
        assert r.gene_name == "PfEMP1"
        assert r.gene_type == "protein coding"

    def test_html_tags_stripped_from_fields(self) -> None:
        doc = _make_doc(
            gene_id="<em>PF3D7_0100100</em>",
            product="<em>erythrocyte</em> membrane protein",
            gene_name="<b>PfEMP1</b>",
        )
        results = parse_site_search_docs([doc])
        assert results[0].gene_id == "PF3D7_0100100"
        assert results[0].product == "erythrocyte membrane protein"
        assert results[0].gene_name == "PfEMP1"

    def test_fallback_to_primary_key_list(self) -> None:
        doc = SiteSearchDocument(
            wdk_primary_key_string="",
            primary_key=["PF3D7_0200200"],
        )
        results = parse_site_search_docs([doc])
        assert results[0].gene_id == "PF3D7_0200200"

    def test_skip_doc_without_gene_id(self) -> None:
        doc = SiteSearchDocument(
            wdk_primary_key_string="",
            primary_key=[],
        )
        results = parse_site_search_docs([doc])
        assert results == []

    def test_missing_summary_field_data(self) -> None:
        doc = SiteSearchDocument(wdk_primary_key_string="PF3D7_0100100")
        results = parse_site_search_docs([doc])
        assert len(results) == 1
        assert results[0].gene_id == "PF3D7_0100100"
        assert results[0].organism == ""
        assert results[0].product == ""

    def test_hyperlink_name_used_as_display_name(self) -> None:
        doc = _make_doc(
            extra_fields={"hyperlink_name": "My Gene Display Name"},
        )
        results = parse_site_search_docs([doc])
        assert results[0].display_name == "My Gene Display Name"

    def test_display_name_fallback_chain(self) -> None:
        # No hyperlinkName, no gene_name => falls back to product
        doc = _make_doc(gene_name="")
        results = parse_site_search_docs([doc])
        assert results[0].display_name == "erythrocyte membrane protein"

    def test_display_name_fallback_to_gene_name(self) -> None:
        doc = _make_doc(gene_name="MyGene")
        results = parse_site_search_docs([doc])
        assert results[0].display_name == "MyGene"

    def test_found_in_fields_parsed(self) -> None:
        doc = _make_doc(
            extra_fields={
                "found_in_fields": {
                    "TEXT__gene_product": ["match1"],
                    "MULTITEXT__gene_Notes": ["note1"],
                }
            }
        )
        results = parse_site_search_docs([doc])
        matched = results[0].matched_fields
        assert isinstance(matched, list)
        assert "gene_product" in matched
        assert "gene_Notes" in matched

    def test_found_in_fields_skips_empty_values(self) -> None:
        doc = _make_doc(
            extra_fields={
                "found_in_fields": {
                    "TEXT__gene_product": [],  # empty => skip
                    "TEXT__gene_name": ["match"],
                }
            }
        )
        results = parse_site_search_docs([doc])
        matched = results[0].matched_fields
        assert isinstance(matched, list)
        assert "gene_product" not in matched
        assert "gene_name" in matched

    def test_organism_fallback_to_doc_level(self) -> None:
        """When summary organism is empty, fall back to doc-level organism."""
        doc = SiteSearchDocument(
            wdk_primary_key_string="PF3D7_0100100",
            organism=["Toxoplasma gondii ME49"],
        )
        results = parse_site_search_docs([doc])
        assert results[0].organism == "Toxoplasma gondii ME49"

    def test_multiple_docs(self) -> None:
        docs = [
            _make_doc(gene_id="GENE_A"),
            _make_doc(gene_id="GENE_B"),
            _make_doc(gene_id="GENE_C"),
        ]
        results = parse_site_search_docs(docs)
        assert len(results) == 3
        assert [r.gene_id for r in results] == ["GENE_A", "GENE_B", "GENE_C"]


# ---------------------------------------------------------------------------
# fetch_site_search_genes
# ---------------------------------------------------------------------------


def _make_response(
    total_count: int = 0,
    documents: list[SiteSearchDocument] | None = None,
    organism_counts: dict[str, int] | None = None,
) -> SiteSearchResponse:
    return SiteSearchResponse(
        search_results=SiteSearchResults(
            total_count=total_count,
            documents=documents or [],
        ),
        organism_counts=organism_counts or {},
    )


class TestFetchSiteSearchGenes:
    """Tests for the async site-search wrapper."""

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.get_site_router",
    )
    async def test_basic_fetch(self, mock_get_router: MagicMock) -> None:
        mock_search = AsyncMock(
            return_value=_make_response(
                total_count=1,
                documents=[
                    SiteSearchDocument(
                        wdk_primary_key_string="PF3D7_0100100",
                        summary_field_data={
                            "TEXT__gene_organism_full": "Plasmodium falciparum 3D7",
                            "TEXT__gene_product": "some product",
                            "TEXT__gene_name": "SomeName",
                            "TEXT__gene_type": "protein coding",
                        },
                    )
                ],
                organism_counts={
                    "Plasmodium falciparum 3D7": 100,
                    "Plasmodium vivax P01": 10,
                },
            )
        )
        mock_get_router.return_value.get_site_search_client.return_value.search = (
            mock_search
        )

        results, organisms, total = await fetch_site_search_genes("plasmodb", "kinase")
        assert len(results) == 1
        assert results[0].gene_id == "PF3D7_0100100"
        assert total == 1
        assert "Plasmodium falciparum 3D7" in organisms
        assert "Plasmodium vivax P01" in organisms

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.get_site_router",
    )
    async def test_empty_response(self, mock_get_router: MagicMock) -> None:
        mock_search = AsyncMock(return_value=_make_response())
        mock_get_router.return_value.get_site_search_client.return_value.search = (
            mock_search
        )

        results, organisms, total = await fetch_site_search_genes("plasmodb", "zzz")
        assert results == []
        assert organisms == []
        assert total == 0

    @patch(
        "veupath_chatbot.services.gene_lookup.site_search.get_site_router",
    )
    async def test_organism_counts_sorted(self, mock_get_router: MagicMock) -> None:
        mock_search = AsyncMock(
            return_value=_make_response(
                organism_counts={
                    "Zzzorganism": 5,
                    "Aaaorganism": 10,
                    "Mmmorganism": 3,
                }
            )
        )
        mock_get_router.return_value.get_site_search_client.return_value.search = (
            mock_search
        )

        _, organisms, _ = await fetch_site_search_genes("plasmodb", "kinase")
        assert organisms == ["Aaaorganism", "Mmmorganism", "Zzzorganism"]


class TestSiteSearchFetchLimit:
    def test_limit_is_50(self) -> None:
        assert SITE_SEARCH_FETCH_LIMIT == 50
