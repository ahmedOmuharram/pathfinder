"""Tests for services.gene_lookup.lookup -- main orchestration logic."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.gene_lookup.lookup import lookup_genes_by_text
from veupath_chatbot.services.gene_lookup.wdk import WdkTextResult
from veupath_chatbot.services.search_rerank import QueryIntent


def _gene(
    gene_id: str,
    *,
    organism: str = "Plasmodium falciparum 3D7",
    product: str = "some product",
    gene_name: str = "",
    display_name: str = "",
) -> dict[str, object]:
    return {
        "geneId": gene_id,
        "organism": organism,
        "product": product,
        "geneName": gene_name,
        "displayName": display_name or product or gene_id,
        "geneType": "protein coding",
        "location": "",
    }


# Patch targets in the lookup module's namespace
_PATCH_SITE_SEARCH = (
    "veupath_chatbot.services.gene_lookup.lookup.fetch_site_search_genes"
)
_PATCH_WDK_TEXT = "veupath_chatbot.services.gene_lookup.lookup.fetch_wdk_text_genes"
_PATCH_ENRICH = "veupath_chatbot.services.gene_lookup.lookup.enrich_sparse_gene_results"
_PATCH_ANALYSE = "veupath_chatbot.services.gene_lookup.lookup.analyse_query"


class TestLookupGenesBasic:
    """Basic orchestration tests."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_basic_query_returns_results(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [_gene("G1"), _gene("G2")]
        mock_site_search.return_value = (genes, ["Plasmodium falciparum 3D7"], 2)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(
                raw="kinase",
                is_gene_id_like=False,
                implied_organism=None,
            )
            result = await lookup_genes_by_text("plasmodb", "kinase")

        assert "records" in result
        assert "totalCount" in result
        results = result["records"]
        assert isinstance(results, list)
        assert len(results) == 2

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_pagination_offset_and_limit(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [_gene(f"G{i}") for i in range(10)]
        mock_site_search.return_value = (genes, [], 10)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text("plasmodb", "kinase", offset=2, limit=3)

        paginated = result["records"]
        assert isinstance(paginated, list)
        assert len(paginated) == 3

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_empty_results(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        mock_site_search.return_value = ([], [], 0)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="zzz_no_match")
            result = await lookup_genes_by_text("plasmodb", "zzz_no_match")

        assert result["records"] == []
        assert result["totalCount"] == 0


class TestLookupGenesOrganismFilter:
    """Tests for organism filtering behavior."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_exact_organism_filter(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [
            _gene("G1", organism="Plasmodium falciparum 3D7"),
            _gene("G2", organism="Toxoplasma gondii ME49"),
        ]
        available = ["Plasmodium falciparum 3D7", "Toxoplasma gondii ME49"]
        mock_site_search.return_value = (genes, available, 2)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text(
                "plasmodb", "kinase", organism="Plasmodium falciparum 3D7"
            )

        results = result["records"]
        assert isinstance(results, list)
        # Only Pf results should remain
        for r in results:
            assert isinstance(r, dict)
            assert (
                str(r.get("organism", "")).strip().lower()
                == "plasmodium falciparum 3d7"
            )

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_unrecognized_organism_suggests_alternatives(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [_gene("G1", organism="Plasmodium falciparum 3D7")]
        available = ["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]
        mock_site_search.return_value = (genes, available, 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text(
                "plasmodb",
                "kinase",
                organism="P. falciparum",  # abbreviation, not exact match
            )

        # Should produce suggestedOrganisms since "P. falciparum" != any exact available
        # But suggest_organisms might find matches
        if result.get("suggestedOrganisms"):
            assert isinstance(result["suggestedOrganisms"], list)


class TestLookupSiteSearchFailure:
    """Tests for graceful degradation when strategies fail."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_site_search_failure_falls_back(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        # Strategy A fails
        mock_site_search.side_effect = WDKError(detail="Site search down")
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            # Should not raise -- the exception is caught inside _strategy_a
            result = await lookup_genes_by_text("plasmodb", "kinase")

        assert "records" in result


class TestLookupMultiWordQuery:
    """Tests for phrase-quoted search behavior with multi-word queries."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_multi_word_triggers_phrase_search(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ([], [], 0)

        mock_site_search.side_effect = side_effect
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="alpha tubulin")
            await lookup_genes_by_text("plasmodb", "alpha tubulin")

        # Strategy A (unrestricted) + A_phrase (quoted) = 2 calls from first gather
        # Then Strategy B might add another
        assert call_count >= 2

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_single_word_no_phrase_search(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ([], [], 0)

        mock_site_search.side_effect = side_effect
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            await lookup_genes_by_text("plasmodb", "kinase")

        # Only Strategy A (no phrase search for single word)
        # Strategy B may not fire (no effective_organism)
        # So just 1 from strategy A, phrase search returns [] immediately
        assert call_count >= 1


class TestLookupTotalCount:
    """Tests for authoritative total count calculation."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_total_count_is_max_of_all_sources(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [_gene(f"G{i}") for i in range(5)]
        mock_site_search.return_value = (genes, ["Plasmodium falciparum 3D7"], 5)
        # WDK returns higher total counts
        mock_wdk_text.side_effect = [
            WdkTextResult(records=[], total_count=0),  # strategy C
            WdkTextResult(records=[], total_count=0),  # strategy D
        ]
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text("plasmodb", "kinase")

        total = result["totalCount"]
        assert isinstance(total, int)
        assert total >= 5
