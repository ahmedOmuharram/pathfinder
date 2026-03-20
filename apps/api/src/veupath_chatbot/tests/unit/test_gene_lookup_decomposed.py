"""Tests for decomposed helpers in services.gene_lookup.lookup.

Each test class targets one of the extracted private helpers:
- _run_primary_searches
- _run_supplementary_searches
- _merge_and_rank
- _apply_organism_filter
- _build_response

These tests validate that the helpers compose correctly and that the
overall lookup_genes_by_text behavior is preserved after decomposition.
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.services.gene_lookup.lookup import (
    _apply_organism_filter,
    _build_response,
    _merge_and_rank,
    _run_primary_searches,
    _run_supplementary_searches,
    lookup_genes_by_text,
)
from veupath_chatbot.services.gene_lookup.wdk import WdkTextResult
from veupath_chatbot.services.search_rerank import QueryIntent


def _gene(
    gene_id: str,
    *,
    organism: str = "Plasmodium falciparum 3D7",
    product: str = "some product",
    gene_name: str = "",
    display_name: str = "",
    matched_fields: list[str] | None = None,
) -> dict[str, object]:
    return {
        "geneId": gene_id,
        "organism": organism,
        "product": product,
        "geneName": gene_name,
        "displayName": display_name or product or gene_id,
        "geneType": "protein coding",
        "location": "",
        "matchedFields": matched_fields or [],
    }


# ── Patch targets ──────────────────────────────────────────────────────
_MOD = "veupath_chatbot.services.gene_lookup.lookup"
_PATCH_SITE_SEARCH = f"{_MOD}.fetch_site_search_genes"
_PATCH_WDK_TEXT = f"{_MOD}.fetch_wdk_text_genes"
_PATCH_ENRICH = f"{_MOD}.enrich_sparse_gene_results"
_PATCH_ANALYSE = f"{_MOD}.analyse_query"


# ── _run_primary_searches ──────────────────────────────────────────────


class TestRunPrimarySearches:
    """Tests for _run_primary_searches helper."""

    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_single_word_returns_results_and_organisms(
        self,
        mock_site_search: AsyncMock,
    ) -> None:
        genes = [_gene("G1"), _gene("G2")]
        available = ["Plasmodium falciparum 3D7"]
        mock_site_search.return_value = (genes, available, 2)

        results, orgs, total = await _run_primary_searches(
            "plasmodb",
            "kinase",
            is_multi_word=False,
        )
        assert len(results) == 2
        assert orgs == available
        assert total == 2

    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_multi_word_merges_phrase_results_first(
        self,
        mock_site_search: AsyncMock,
    ) -> None:
        call_queries: list[str] = []

        async def side_effect(site_id: str, query: str, **kwargs):
            call_queries.append(query)
            if query.startswith('"'):
                return ([_gene("PHRASE_HIT")], [], 1)
            return ([_gene("BROAD_HIT")], ["Org A"], 5)

        mock_site_search.side_effect = side_effect

        results, _orgs, _total = await _run_primary_searches(
            "plasmodb",
            "alpha tubulin",
            is_multi_word=True,
        )
        # Phrase results should come first
        assert len(results) >= 2
        assert results[0]["geneId"] == "PHRASE_HIT"
        assert results[1]["geneId"] == "BROAD_HIT"
        # Two calls: unrestricted + phrase-quoted
        assert len(call_queries) == 2

    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_site_search_failure_returns_empty(
        self,
        mock_site_search: AsyncMock,
    ) -> None:
        mock_site_search.side_effect = RuntimeError("boom")

        results, orgs, total = await _run_primary_searches(
            "plasmodb",
            "kinase",
            is_multi_word=False,
        )
        assert results == []
        assert orgs == []
        assert total == 0

    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_phrase_search_failure_still_returns_broad(
        self,
        mock_site_search: AsyncMock,
    ) -> None:
        call_count = 0

        async def side_effect(site_id: str, query: str, **kwargs):
            nonlocal call_count
            call_count += 1
            if query.startswith('"'):
                msg = "phrase search broke"
                raise RuntimeError(msg)
            return ([_gene("G1")], ["Org A"], 1)

        mock_site_search.side_effect = side_effect

        results, _orgs, _total = await _run_primary_searches(
            "plasmodb",
            "alpha tubulin",
            is_multi_word=True,
        )
        assert len(results) == 1
        assert results[0]["geneId"] == "G1"


# ── _run_supplementary_searches ────────────────────────────────────────


class TestRunSupplementarySearches:
    """Tests for _run_supplementary_searches helper."""

    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_no_organism_skips_all(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
    ) -> None:
        intent = QueryIntent(raw="kinase")
        org_results, wdk_id, wdk_broad = await _run_supplementary_searches(
            "plasmodb",
            "kinase",
            intent,
            effective_organism=None,
            explicit_organism=None,
            needed=20,
        )
        assert org_results == []
        assert wdk_id.records == []
        assert wdk_broad.records == []
        mock_site_search.assert_not_called()
        mock_wdk_text.assert_not_called()

    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_with_effective_organism_fires_strategy_b(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
    ) -> None:
        intent = QueryIntent(raw="kinase")
        mock_site_search.return_value = ([_gene("ORG_HIT")], [], 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)

        org_results, _wdk_id, _wdk_broad = await _run_supplementary_searches(
            "plasmodb",
            "kinase",
            intent,
            effective_organism="Plasmodium falciparum 3D7",
            explicit_organism=None,
            needed=20,
        )
        assert len(org_results) == 1
        assert org_results[0]["geneId"] == "ORG_HIT"

    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_with_wildcard_ids_fires_strategy_c(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
    ) -> None:
        intent = QueryIntent(
            raw="PF3D7_01",
            is_gene_id_like=True,
            wildcard_ids=("PF3D7_01*",),
        )
        wdk_id_result = WdkTextResult(records=[_gene("PF3D7_0100100")], total_count=5)
        mock_site_search.return_value = ([], [], 0)
        mock_wdk_text.return_value = wdk_id_result

        _org_results, wdk_id, _wdk_broad = await _run_supplementary_searches(
            "plasmodb",
            "PF3D7_01",
            intent,
            effective_organism="Plasmodium falciparum 3D7",
            explicit_organism=None,
            needed=20,
        )
        assert wdk_id.total_count == 5

    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_with_explicit_organism_fires_strategy_d(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
    ) -> None:
        intent = QueryIntent(raw="kinase")
        wdk_broad_result = WdkTextResult(records=[_gene("WDK_BROAD")], total_count=100)
        mock_site_search.return_value = ([], [], 0)
        mock_wdk_text.return_value = wdk_broad_result

        _org_results, _wdk_id, wdk_broad = await _run_supplementary_searches(
            "plasmodb",
            "kinase",
            intent,
            effective_organism="Plasmodium falciparum 3D7",
            explicit_organism="Plasmodium falciparum 3D7",
            needed=20,
        )
        assert wdk_broad.total_count == 100

    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_strategy_b_failure_returns_empty(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
    ) -> None:
        intent = QueryIntent(raw="kinase")
        mock_site_search.side_effect = RuntimeError("boom")
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)

        org_results, _wdk_id, _wdk_broad = await _run_supplementary_searches(
            "plasmodb",
            "kinase",
            intent,
            effective_organism="Plasmodium falciparum 3D7",
            explicit_organism=None,
            needed=20,
        )
        assert org_results == []


# ── _merge_and_rank ────────────────────────────────────────────────────


class TestMergeAndRank:
    """Tests for _merge_and_rank helper."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    async def test_deduplicates_by_gene_id(
        self,
        mock_enrich: AsyncMock,
    ) -> None:
        mock_enrich.side_effect = lambda _site, results, _lim: results

        raw = [_gene("G1"), _gene("G1"), _gene("G2")]
        results = await _merge_and_rank("plasmodb", "kinase", raw)
        gene_ids = [r["geneId"] for r in results]
        assert len(gene_ids) == 2
        assert set(gene_ids) == {"G1", "G2"}

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    async def test_empty_input_returns_empty(
        self,
        mock_enrich: AsyncMock,
    ) -> None:
        mock_enrich.side_effect = lambda _site, results, _lim: results

        results = await _merge_and_rank("plasmodb", "kinase", [])
        assert results == []

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    async def test_results_sorted_by_relevance(
        self,
        mock_enrich: AsyncMock,
    ) -> None:
        mock_enrich.side_effect = lambda _site, results, _lim: results

        # "kinase" should score higher for gene with product "kinase" than "other"
        raw = [
            _gene("G1", product="something else entirely"),
            _gene("G2", product="kinase"),
        ]
        results = await _merge_and_rank("plasmodb", "kinase", raw)
        # G2 should rank higher because product exactly matches query
        assert results[0]["geneId"] == "G2"


# ── _apply_organism_filter ─────────────────────────────────────────────


class TestApplyOrganismFilter:
    """Tests for _apply_organism_filter helper."""

    def test_no_organism_returns_all(self) -> None:
        genes = [_gene("G1"), _gene("G2")]
        filtered, suggested = _apply_organism_filter(
            genes,
            organism=None,
            explicit_organism=None,
            available_organisms=["Plasmodium falciparum 3D7"],
        )
        assert len(filtered) == 2
        assert suggested is None

    def test_exact_organism_filters(self) -> None:
        genes = [
            _gene("G1", organism="Plasmodium falciparum 3D7"),
            _gene("G2", organism="Toxoplasma gondii ME49"),
        ]
        filtered, suggested = _apply_organism_filter(
            genes,
            organism="Plasmodium falciparum 3D7",
            explicit_organism="Plasmodium falciparum 3D7",
            available_organisms=["Plasmodium falciparum 3D7", "Toxoplasma gondii ME49"],
        )
        assert len(filtered) == 1
        assert filtered[0]["geneId"] == "G1"
        assert suggested is None

    def test_unrecognized_organism_suggests_alternatives(self) -> None:
        genes = [_gene("G1", organism="Plasmodium falciparum 3D7")]
        available = ["Plasmodium falciparum 3D7", "Plasmodium vivax P01"]
        _filtered, suggested = _apply_organism_filter(
            genes,
            organism="P. falciparum",
            explicit_organism=None,
            available_organisms=available,
        )
        # suggest_organisms should find fuzzy matches
        assert suggested is not None
        assert isinstance(suggested, list)

    def test_unrecognized_organism_no_fuzzy_match_returns_empty_with_top10(
        self,
    ) -> None:
        genes = [_gene("G1")]
        available = ["Org A", "Org B", "Org C"]
        filtered, suggested = _apply_organism_filter(
            genes,
            organism="zzz_no_match_organism_xyz",
            explicit_organism=None,
            available_organisms=available,
        )
        assert filtered == []
        assert suggested is not None
        assert len(suggested) <= 10


# ── _build_response ────────────────────────────────────────────────────


class TestBuildResponse:
    """Tests for _build_response helper."""

    def test_basic_response_shape(self) -> None:
        paginated = [_gene("G1"), _gene("G2")]
        resp = _build_response(
            paginated=paginated,
            total_count=10,
            wdk_totals=(5, 20),
            suggested_organisms=None,
        )
        assert resp["records"] is paginated
        # Authoritative total = max(10, 5, 20)
        assert resp["totalCount"] == 20
        assert "suggestedOrganisms" not in resp

    def test_includes_suggested_organisms(self) -> None:
        resp = _build_response(
            paginated=[],
            total_count=0,
            wdk_totals=(0, 0),
            suggested_organisms=["Org A", "Org B"],
        )
        assert resp["suggestedOrganisms"] == ["Org A", "Org B"]

    def test_total_count_is_max_of_all_sources(self) -> None:
        resp = _build_response(
            paginated=[_gene("G1")],
            total_count=3,
            wdk_totals=(50, 100),
            suggested_organisms=None,
        )
        assert resp["totalCount"] == 100

    def test_total_count_from_results_length(self) -> None:
        resp = _build_response(
            paginated=[_gene(f"G{i}") for i in range(5)],
            total_count=200,
            wdk_totals=(10, 15),
            suggested_organisms=None,
        )
        # max(200, 10, 15) = 200
        assert resp["totalCount"] == 200


# ── Integration: ensure lookup_genes_by_text still works end-to-end ───


class TestLookupGenesAfterDecomposition:
    """Verify that the public API is unchanged after decomposition."""

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_basic_lookup_still_works(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        genes = [_gene("G1"), _gene("G2"), _gene("G3")]
        mock_site_search.return_value = (genes, ["Plasmodium falciparum 3D7"], 3)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(_PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text("plasmodb", "kinase")

        assert "records" in result
        assert "totalCount" in result
        assert isinstance(result["records"], list)

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_organism_filter_with_decomposed_helpers(
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
                "plasmodb",
                "kinase",
                organism="Plasmodium falciparum 3D7",
            )

        results = result["records"]
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, dict)
            assert (
                str(r.get("organism", "")).strip().lower()
                == "plasmodium falciparum 3d7"
            )

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_pagination_with_decomposed_helpers(
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
            result = await lookup_genes_by_text(
                "plasmodb",
                "kinase",
                offset=3,
                limit=2,
            )

        assert isinstance(result["records"], list)
        assert len(result["records"]) == 2
