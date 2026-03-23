"""Edge-case tests for the gene lookup module.

Covers:
- Organism matching with Unicode characters
- Gene IDs with special characters
- Scoring with tied scores
- Site search with empty/edge-case inputs
- WDK text search edge cases
- Enrichment with all-None fields
- Lookup with limit=0
- Dedup determinism
"""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.site_search_client import SiteSearchDocument
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordInstance
from veupath_chatbot.services.gene_lookup.enrich import (
    enrich_sparse_gene_results,
)
from veupath_chatbot.services.gene_lookup.lookup import lookup_genes_by_text
from veupath_chatbot.services.gene_lookup.organism import (
    normalize_organism,
    score_organism_match,
    suggest_organisms,
)
from veupath_chatbot.services.gene_lookup.result import (
    GeneResult,
)
from veupath_chatbot.services.gene_lookup.scoring import score_gene_relevance
from veupath_chatbot.services.gene_lookup.site_search import (
    parse_site_search_docs,
)
from veupath_chatbot.services.gene_lookup.wdk import (
    GeneResolveResult,
    WdkTextResult,
    _parse_wdk_record,
)
from veupath_chatbot.services.search_rerank import (
    QueryIntent,
    ScoredResult,
    dedup_and_sort,
    score_text_match,
)

# ---------------------------------------------------------------------------
# Organism matching: Unicode characters
# ---------------------------------------------------------------------------


class TestOrganismMatchUnicode:
    """Organism matching with accented/Unicode names."""

    def test_accented_genus_exact(self) -> None:
        """Accented characters should match exactly after lowercasing."""
        score = score_organism_match("Leishmania donovani", "Leishmania donovani")
        assert score == 1.0

    def test_unicode_normalisation_not_applied(self) -> None:
        """If the query has a combining accent, it won't match the precomposed form.

        This documents current behavior: no Unicode normalization is performed.
        """
        # e with combining acute vs precomposed e-acute
        query = "Le\u0301ishmania"
        organism = "L\u00e9ishmania donovani"
        score = score_organism_match(query, organism)
        # They look the same visually but the byte sequences differ.
        # Current code does NOT do unicode normalization, so this may not
        # match at 1.0 or even 0.85.
        assert isinstance(score, float)

    def test_suggest_organisms_unicode(self) -> None:
        """suggest_organisms should handle unicode organism names gracefully."""
        orgs = ["Trypanosoma cru\u0301zi", "Plasmodium falciparum 3D7"]
        result = suggest_organisms("trypanosoma", orgs)
        # "trypanosoma" is a substring of the first organism
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Gene IDs with special characters
# ---------------------------------------------------------------------------


class TestGeneIdSpecialChars:
    """Gene IDs with underscores, dots, hyphens, and other special chars."""

    def test_gene_id_with_dot(self) -> None:
        result = GeneResult(gene_id="TGME49_200.1")
        assert result.gene_id == "TGME49_200.1"

    def test_gene_id_with_hyphen(self) -> None:
        result = GeneResult(gene_id="PF3D7-0100100")
        assert result.gene_id == "PF3D7-0100100"

    def test_gene_id_with_colon(self) -> None:
        result = GeneResult(gene_id="GeneDB:PF3D7_0100100")
        assert result.gene_id == "GeneDB:PF3D7_0100100"

    def test_score_gene_id_with_dot(self) -> None:
        """score_text_match should handle gene IDs with dots."""
        score = score_text_match("TGME49_200.1", "TGME49_200.1")
        assert score == 1.0

    def test_score_gene_id_prefix_with_dot(self) -> None:
        score = score_text_match("TGME49_200", "TGME49_200.1")
        assert score == 0.95  # prefix match

    def test_wdk_parse_gene_id_with_special_chars(self) -> None:
        rec = WDKRecordInstance(
            attributes={
                "gene_source_id": "PF3D7.0100100-v2",
                "primary_key": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result.gene_id == "PF3D7.0100100-v2"


# ---------------------------------------------------------------------------
# Scoring determinism with tied scores
# ---------------------------------------------------------------------------


class TestScoringTiedScores:
    """Dedup and sort should be deterministic when scores are tied."""

    def test_tied_scores_dedup_keeps_higher(self) -> None:
        """When two entries for the same key have equal scores, the first wins."""
        results = [
            ScoredResult(result=GeneResult(gene_id="a"), score=0.5),
            ScoredResult(result=GeneResult(gene_id="a"), score=0.5),
        ]
        deduped = dedup_and_sort(results, key_fn=lambda r: r.gene_id)
        # Only one entry kept since they have the same key
        assert len(deduped) == 1

    def test_tied_scores_different_keys_stable(self) -> None:
        """Different keys with the same score should all be present."""
        results = [
            ScoredResult(result=GeneResult(gene_id="a"), score=0.5),
            ScoredResult(result=GeneResult(gene_id="b"), score=0.5),
            ScoredResult(result=GeneResult(gene_id="c"), score=0.5),
        ]
        deduped = dedup_and_sort(results, key_fn=lambda r: r.gene_id)
        assert len(deduped) == 3

    def test_gene_relevance_scores_are_deterministic(self) -> None:
        """Same inputs should always produce the same score."""
        result = GeneResult(
            gene_id="PF3D7_0100100",
            gene_name="CSP",
            display_name="CSP",
            organism="Plasmodium falciparum 3D7",
            product="circumsporozoite protein",
        )
        score1 = score_gene_relevance("CSP", result)
        score2 = score_gene_relevance("CSP", result)
        assert score1 == score2


# ---------------------------------------------------------------------------
# Site search edge cases
# ---------------------------------------------------------------------------


class TestSiteSearchEdgeCases:
    """Edge cases in site-search document parsing."""

    def test_empty_doc_list(self) -> None:
        results = parse_site_search_docs([])
        assert results == []

    def test_doc_with_html_in_gene_id(self) -> None:
        """Gene IDs wrapped in <em> tags should be cleaned."""
        docs = [
            SiteSearchDocument(
                wdk_primary_key_string="<em>PF3D7</em>_0100100",
            )
        ]
        results = parse_site_search_docs(docs)
        assert len(results) == 1
        assert results[0].gene_id == "PF3D7_0100100"

    def test_doc_with_only_whitespace_gene_id(self) -> None:
        """Whitespace-only gene ID should be skipped."""
        docs = [
            SiteSearchDocument(
                wdk_primary_key_string="   ",
                primary_key=[],
            )
        ]
        results = parse_site_search_docs(docs)
        assert results == []

    def test_doc_with_empty_summary_field_data(self) -> None:
        """Empty summaryFieldData should be treated as missing (all fields empty)."""
        docs = [
            SiteSearchDocument(
                wdk_primary_key_string="GENE_X",
            )
        ]
        results = parse_site_search_docs(docs)
        assert len(results) == 1
        assert results[0].gene_id == "GENE_X"
        assert results[0].organism == ""

    def test_doc_found_in_fields_empty(self) -> None:
        """Empty found_in_fields should result in empty matchedFields."""
        docs = [
            SiteSearchDocument(
                wdk_primary_key_string="GENE_X",
            )
        ]
        results = parse_site_search_docs(docs)
        assert results[0].matched_fields == []

    def test_doc_found_in_fields_skips_empty_lists(self) -> None:
        """Field entries with empty lists should not appear in matchedFields."""
        docs = [
            SiteSearchDocument(
                wdk_primary_key_string="GENE_X",
                found_in_fields={
                    "TEXT__gene_product": [],
                    "TEXT__gene_name": ["valid"],
                },
            )
        ]
        results = parse_site_search_docs(docs)
        matched = results[0].matched_fields
        assert isinstance(matched, list)
        assert "gene_name" in matched
        assert "gene_product" not in matched


# ---------------------------------------------------------------------------
# WDK text search edge cases
# ---------------------------------------------------------------------------


class TestWdkRecordEdgeCases:
    """Edge cases in WDK record parsing."""

    def test_all_empty_attributes(self) -> None:
        """Record with all empty/None attributes should still produce a result."""
        rec = WDKRecordInstance(
            id=[{"name": "gene_source_id", "value": "FALLBACK_ID"}],
            attributes={
                "primary_key": "",
                "gene_source_id": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result.gene_id == "FALLBACK_ID"

    def test_none_gene_name_raw(self) -> None:
        """When gene_name is None, it should be treated as empty."""
        rec = WDKRecordInstance(
            attributes={
                "primary_key": "PK",
                "gene_source_id": "SRC",
                "gene_name": None,
                "gene_product": None,
                "organism": None,
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result.gene_name == ""
        assert result.product == ""
        assert result.organism == ""

    def test_empty_id_list_falls_back_to_primary_key(self) -> None:
        """When id list is empty, gene_id falls back to primary_key attribute."""
        rec = WDKRecordInstance(
            attributes={
                "primary_key": "PK_VAL",
                "gene_source_id": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result.gene_id == "PK_VAL"


# ---------------------------------------------------------------------------
# Enrichment edge cases
# ---------------------------------------------------------------------------


class TestEnrichEdgeCases:
    """Edge cases in gene result enrichment."""

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_all_genes_have_none_fields(self, mock_resolve: AsyncMock) -> None:
        """When all genes are missing both organism and product, all should be enriched."""
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(gene_id="G1", organism="Pf", product="prod1"),
                GeneResult(gene_id="G2", organism="Tg", product="prod2"),
            ],
            total_count=2,
        )
        results: list[GeneResult] = [
            GeneResult(gene_id="G1"),
            GeneResult(gene_id="G2"),
        ]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0].organism == "Pf"
        assert enriched[1].organism == "Tg"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enrichment_limit_zero(self, mock_resolve: AsyncMock) -> None:
        """limit=0 should return empty list after enrichment."""
        mock_resolve.return_value = GeneResolveResult(
            records=[
                GeneResult(gene_id="G1", organism="Pf", product="prod1"),
            ],
            total_count=1,
        )
        results: list[GeneResult] = [GeneResult(gene_id="G1")]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 0)
        assert enriched == []

    async def test_enrichment_empty_results(self) -> None:
        """Empty results list should pass through without WDK calls."""
        enriched = await enrich_sparse_gene_results("plasmodb", [], 10)
        assert enriched == []


# ---------------------------------------------------------------------------
# Lookup with limit=0 and offset edge cases
# ---------------------------------------------------------------------------


class TestLookupEdgeCases:
    """Edge cases in the main lookup orchestration."""

    _PATCH_SITE_SEARCH = (
        "veupath_chatbot.services.gene_lookup.lookup.fetch_site_search_genes"
    )
    _PATCH_WDK_TEXT = "veupath_chatbot.services.gene_lookup.lookup.fetch_wdk_text_genes"
    _PATCH_ENRICH = (
        "veupath_chatbot.services.gene_lookup.lookup.enrich_sparse_gene_results"
    )
    _PATCH_ANALYSE = "veupath_chatbot.services.gene_lookup.lookup.analyse_query"

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_limit_zero_returns_empty_results(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        """limit=0 should return an empty paginated set."""
        genes = [
            GeneResult(
                gene_id="G1",
                organism="Pf",
                product="p",
                display_name="p",
            ),
        ]
        mock_site_search.return_value = (genes, [], 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(self._PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text("plasmodb", "kinase", limit=0)

        assert len(result.records) == 0

    @patch(_PATCH_ENRICH, new_callable=AsyncMock)
    @patch(_PATCH_WDK_TEXT, new_callable=AsyncMock)
    @patch(_PATCH_SITE_SEARCH, new_callable=AsyncMock)
    async def test_offset_beyond_results(
        self,
        mock_site_search: AsyncMock,
        mock_wdk_text: AsyncMock,
        mock_enrich: AsyncMock,
    ) -> None:
        """offset beyond total results should return empty."""
        genes = [
            GeneResult(
                gene_id="G1",
                organism="Pf",
                product="p",
                display_name="p",
            ),
        ]
        mock_site_search.return_value = (genes, [], 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(self._PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text(
                "plasmodb", "kinase", offset=100, limit=10
            )

        assert len(result.records) == 0


# ---------------------------------------------------------------------------
# Normalize organism edge cases
# ---------------------------------------------------------------------------


class TestNormalizeOrganismEdgeCases:
    """Additional edge cases for normalize_organism."""

    def test_json_array_with_html_nested(self) -> None:
        result = normalize_organism('["<b>Pf</b> 3D7"]')
        assert result == "Pf 3D7"

    def test_json_array_with_only_empty_string(self) -> None:
        result = normalize_organism('[""]')
        assert result == ""

    def test_json_non_array_object(self) -> None:
        """JSON object (not array) should be returned as-is after strip."""
        result = normalize_organism('{"name": "Pf"}')
        assert result == '{"name": "Pf"}'

    def test_json_array_starts_but_invalid(self) -> None:
        """Starts with [ but is invalid JSON."""
        result = normalize_organism("[broken")
        assert result == "[broken"

    def test_brackets_not_json(self) -> None:
        """Brackets that are not JSON should pass through."""
        result = normalize_organism("[abc")
        assert result == "[abc"


# ---------------------------------------------------------------------------
# Organism score edge cases
# ---------------------------------------------------------------------------


class TestOrganismScoreEdgeCases:
    """Edge cases for score_organism_match."""

    def test_single_char_organism(self) -> None:
        """Single-character organism should not crash."""
        score = score_organism_match("a", "a")
        assert score == 1.0

    def test_single_word_organism(self) -> None:
        """Single-word organism -- gs_initials would be out of range."""
        score = score_organism_match("pf3d7", "Plasmodium")
        # "Plasmodium" has only 1 word, so len(o_words) < 2, compact code skipped
        assert isinstance(score, float)

    def test_organism_code_with_extra_punctuation(self) -> None:
        """Organism code with dots and hyphens stripped."""
        score = score_organism_match("p.f.3d7", "Plasmodium falciparum 3D7")
        assert score >= 0.65  # Should at least get token/partial match

    def test_suggest_organisms_max_suggestions_zero(self) -> None:
        """max_suggestions=0 should return empty list."""
        orgs = ["Plasmodium falciparum 3D7"]
        result = suggest_organisms("Plasmodium", orgs, max_suggestions=0)
        assert result == []

    def test_suggest_organisms_deterministic_tiebreaking(self) -> None:
        """When scores are tied, organisms are sorted alphabetically."""
        orgs = [
            "Plasmodium falciparum 3D7",
            "Plasmodium falciparum IT",
            "Plasmodium falciparum Dd2",
        ]
        result = suggest_organisms("falciparum", orgs)
        # All match at 0.85 (substring). Tiebreaker should be alphabetical.
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# Build gene result edge cases
# ---------------------------------------------------------------------------


class TestGeneResultEdgeCases:
    """Edge cases for GeneResult dataclass."""

    def test_empty_gene_id(self) -> None:
        """Empty gene_id should still produce a result."""
        result = GeneResult(gene_id="")
        assert result.gene_id == ""
        assert result.display_name == ""

    def test_display_name_empty_string_not_defaulted(self) -> None:
        """display_name='' stays empty; transport layer handles fallback."""
        result = GeneResult(gene_id="X", display_name="", product="my product")
        assert result.display_name == ""

    def test_matched_fields_empty_list(self) -> None:
        """Empty list is distinct from None."""
        result = GeneResult(gene_id="X", matched_fields=[])
        assert result.matched_fields == []


# ---------------------------------------------------------------------------
# score_text_match edge cases
# ---------------------------------------------------------------------------


class TestScoreTextMatchEdgeCases:
    """Edge cases for score_text_match."""

    def test_both_empty(self) -> None:
        assert score_text_match("", "") == 0.0

    def test_whitespace_only_query(self) -> None:
        assert score_text_match("   ", "something") == 0.0

    def test_whitespace_only_value(self) -> None:
        assert score_text_match("query", "   ") == 0.0

    def test_very_long_query(self) -> None:
        """Very long query should not crash."""
        long_q = "a" * 10000
        score = score_text_match(long_q, "a" * 10000)
        assert score == 1.0

    def test_case_insensitive_prefix(self) -> None:
        score = score_text_match("pf3d7", "PF3D7_1234500")
        assert score == 0.95


# ---------------------------------------------------------------------------
# score_gene_relevance edge cases
# ---------------------------------------------------------------------------


class TestScoreGeneRelevanceEdgeCases:
    """Edge cases for score_gene_relevance."""

    def test_all_none_fields(self) -> None:
        """Result with all empty values should score 0."""
        score = score_gene_relevance(
            "kinase",
            GeneResult(gene_id=""),
        )
        assert score == pytest.approx(0.0, abs=0.01)

    def test_matched_fields_with_primary_field(self) -> None:
        """matchedFields list with primary field should get quality bonus."""
        score = score_gene_relevance(
            "kinase",
            GeneResult(
                gene_id="X",
                product="kinase",
                matched_fields=["gene_product"],
            ),
        )
        # gene_product is a primary field, so quality bonus should apply
        assert score > 0
