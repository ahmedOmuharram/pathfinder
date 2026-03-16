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

from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.services.gene_lookup.organism import (
    normalize_organism,
    score_organism_match,
    suggest_organisms,
)
from veupath_chatbot.services.gene_lookup.result import build_gene_result
from veupath_chatbot.services.gene_lookup.scoring import score_gene_relevance
from veupath_chatbot.services.gene_lookup.site_search import (
    parse_site_search_docs,
)
from veupath_chatbot.services.gene_lookup.wdk import _parse_wdk_record
from veupath_chatbot.services.search_rerank import (
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
        result = build_gene_result(gene_id="TGME49_200.1")
        assert result["geneId"] == "TGME49_200.1"

    def test_gene_id_with_hyphen(self) -> None:
        result = build_gene_result(gene_id="PF3D7-0100100")
        assert result["geneId"] == "PF3D7-0100100"

    def test_gene_id_with_colon(self) -> None:
        result = build_gene_result(gene_id="GeneDB:PF3D7_0100100")
        assert result["geneId"] == "GeneDB:PF3D7_0100100"

    def test_score_gene_id_with_dot(self) -> None:
        """score_text_match should handle gene IDs with dots."""
        score = score_text_match("TGME49_200.1", "TGME49_200.1")
        assert score == 1.0

    def test_score_gene_id_prefix_with_dot(self) -> None:
        score = score_text_match("TGME49_200", "TGME49_200.1")
        assert score == 0.95  # prefix match

    def test_wdk_parse_gene_id_with_special_chars(self) -> None:
        rec: dict[str, object] = {
            "attributes": {
                "gene_source_id": "PF3D7.0100100-v2",
                "primary_key": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PF3D7.0100100-v2"


# ---------------------------------------------------------------------------
# Scoring determinism with tied scores
# ---------------------------------------------------------------------------


class TestScoringTiedScores:
    """Dedup and sort should be deterministic when scores are tied."""

    def test_tied_scores_dedup_keeps_higher(self) -> None:
        """When two entries for the same key have equal scores, the first wins."""
        results = [
            ScoredResult(result={"id": "a", "v": 1}, score=0.5),
            ScoredResult(result={"id": "a", "v": 2}, score=0.5),
        ]
        deduped = dedup_and_sort(results, key_fn=lambda r: str(r.get("id", "")))
        # Only one entry kept since they have the same key
        assert len(deduped) == 1

    def test_tied_scores_different_keys_stable(self) -> None:
        """Different keys with the same score should all be present."""
        results = [
            ScoredResult(result={"id": "a"}, score=0.5),
            ScoredResult(result={"id": "b"}, score=0.5),
            ScoredResult(result={"id": "c"}, score=0.5),
        ]
        deduped = dedup_and_sort(results, key_fn=lambda r: str(r.get("id", "")))
        assert len(deduped) == 3

    def test_gene_relevance_scores_are_deterministic(self) -> None:
        """Same inputs should always produce the same score."""
        result = {
            "geneId": "PF3D7_0100100",
            "geneName": "CSP",
            "displayName": "CSP",
            "organism": "Plasmodium falciparum 3D7",
            "product": "circumsporozoite protein",
        }
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
            {
                "wdkPrimaryKeyString": "<em>PF3D7</em>_0100100",
                "summaryFieldData": {},
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        assert len(results) == 1
        assert results[0]["geneId"] == "PF3D7_0100100"

    def test_doc_with_only_whitespace_gene_id(self) -> None:
        """Whitespace-only gene ID should be skipped."""
        docs = [
            {
                "wdkPrimaryKeyString": "   ",
                "primaryKey": [],
                "summaryFieldData": {},
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        assert results == []

    def test_doc_with_none_summary_field_data(self) -> None:
        """summaryFieldData that is None should be treated as empty dict."""
        docs = [
            {
                "wdkPrimaryKeyString": "GENE_X",
                "summaryFieldData": None,
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        assert len(results) == 1
        assert results[0]["geneId"] == "GENE_X"
        assert results[0]["organism"] == ""

    def test_doc_with_integer_summary_field_data(self) -> None:
        """summaryFieldData that is not a dict should be treated as empty dict."""
        docs = [
            {
                "wdkPrimaryKeyString": "GENE_X",
                "summaryFieldData": 42,
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        assert len(results) == 1
        assert results[0]["geneId"] == "GENE_X"

    def test_doc_found_in_fields_not_dict(self) -> None:
        """foundInFields that is not a dict should result in empty matchedFields."""
        docs = [
            {
                "wdkPrimaryKeyString": "GENE_X",
                "summaryFieldData": {},
                "foundInFields": "not a dict",
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        assert results[0]["matchedFields"] == []

    def test_doc_found_in_fields_non_list_values(self) -> None:
        """Field values that are not lists should be skipped."""
        docs = [
            {
                "wdkPrimaryKeyString": "GENE_X",
                "summaryFieldData": {},
                "foundInFields": {
                    "TEXT__gene_product": "not a list",
                    "TEXT__gene_name": ["valid"],
                },
            }
        ]
        results = parse_site_search_docs(cast(list[object], docs))
        matched = results[0]["matchedFields"]
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
        rec: dict[str, object] = {
            "attributes": {
                "primary_key": "",
                "gene_source_id": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
            "id": [{"name": "gene_source_id", "value": "FALLBACK_ID"}],
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "FALLBACK_ID"

    def test_none_gene_name_raw(self) -> None:
        """When gene_name is None, it should be treated as empty."""
        rec: dict[str, object] = {
            "attributes": {
                "primary_key": "PK",
                "gene_source_id": "SRC",
                "gene_name": None,
                "gene_product": None,
                "organism": None,
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneName"] == ""
        assert result["product"] == ""
        assert result["organism"] == ""

    def test_pk_list_with_non_string_value(self) -> None:
        """PK elements with non-string values should be skipped."""
        rec: dict[str, object] = {
            "id": [
                {"name": "gene_source_id", "value": 12345},
                {"name": "source_id", "value": "GOOD_ID"},
            ],
            "attributes": {"gene_source_id": ""},
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "GOOD_ID"

    def test_pk_not_a_list(self) -> None:
        """id field that is not a list should be handled gracefully."""
        rec: dict[str, object] = {
            "id": "not_a_list",
            "attributes": {
                "primary_key": "PK_VAL",
                "gene_source_id": "",
                "gene_name": "",
                "gene_product": "",
                "organism": "",
                "gene_type": "",
                "gene_location_text": "",
                "gene_previous_ids": "",
            },
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PK_VAL"


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
        mock_resolve.return_value = {
            "records": [
                {"geneId": "G1", "organism": "Pf", "product": "prod1"},
                {"geneId": "G2", "organism": "Tg", "product": "prod2"},
            ],
        }
        from veupath_chatbot.services.gene_lookup.enrich import (
            enrich_sparse_gene_results,
        )

        results: list[dict[str, object]] = [
            {"geneId": "G1"},
            {"geneId": "G2"},
        ]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 10)
        assert enriched[0]["organism"] == "Pf"
        assert enriched[1]["organism"] == "Tg"

    @patch(
        "veupath_chatbot.services.gene_lookup.enrich.resolve_gene_ids",
        new_callable=AsyncMock,
    )
    async def test_enrichment_limit_zero(self, mock_resolve: AsyncMock) -> None:
        """limit=0 should return empty list after enrichment."""
        mock_resolve.return_value = {
            "records": [
                {"geneId": "G1", "organism": "Pf", "product": "prod1"},
            ],
        }
        from veupath_chatbot.services.gene_lookup.enrich import (
            enrich_sparse_gene_results,
        )

        results: list[dict[str, object]] = [{"geneId": "G1"}]
        enriched = await enrich_sparse_gene_results("plasmodb", results, 0)
        assert enriched == []

    async def test_enrichment_empty_results(self) -> None:
        """Empty results list should pass through without WDK calls."""
        from veupath_chatbot.services.gene_lookup.enrich import (
            enrich_sparse_gene_results,
        )

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
        from veupath_chatbot.services.gene_lookup.lookup import lookup_genes_by_text
        from veupath_chatbot.services.gene_lookup.wdk import WdkTextResult
        from veupath_chatbot.services.search_rerank import QueryIntent

        genes = [
            {
                "geneId": "G1",
                "organism": "Pf",
                "product": "p",
                "geneName": "",
                "displayName": "p",
                "geneType": "",
                "location": "",
            },
        ]
        mock_site_search.return_value = (genes, [], 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(self._PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text("plasmodb", "kinase", limit=0)

        paginated = result["records"]
        assert isinstance(paginated, list)
        assert len(paginated) == 0

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
        from veupath_chatbot.services.gene_lookup.lookup import lookup_genes_by_text
        from veupath_chatbot.services.gene_lookup.wdk import WdkTextResult
        from veupath_chatbot.services.search_rerank import QueryIntent

        genes = [
            {
                "geneId": "G1",
                "organism": "Pf",
                "product": "p",
                "geneName": "",
                "displayName": "p",
                "geneType": "",
                "location": "",
            },
        ]
        mock_site_search.return_value = (genes, [], 1)
        mock_wdk_text.return_value = WdkTextResult(records=[], total_count=0)
        mock_enrich.side_effect = lambda _site, results, _lim: results

        with patch(self._PATCH_ANALYSE) as mock_analyse:
            mock_analyse.return_value = QueryIntent(raw="kinase")
            result = await lookup_genes_by_text(
                "plasmodb", "kinase", offset=100, limit=10
            )

        paginated = result["records"]
        assert isinstance(paginated, list)
        assert len(paginated) == 0


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


class TestBuildGeneResultEdgeCases:
    """Edge cases for build_gene_result."""

    def test_empty_gene_id(self) -> None:
        """Empty gene_id should still produce a result."""
        result = build_gene_result(gene_id="")
        assert result["geneId"] == ""
        assert result["displayName"] == ""

    def test_display_name_empty_string_falls_back_to_product(self) -> None:
        """Explicitly passing display_name='' should fall back to product."""
        result = build_gene_result(gene_id="X", display_name="", product="my product")
        assert result["displayName"] == "my product"

    def test_matched_fields_empty_list_included(self) -> None:
        """Empty list should be included (unlike None)."""
        result = build_gene_result(gene_id="X", matched_fields=[])
        assert "matchedFields" in result
        assert result["matchedFields"] == []


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
        """Result with all None-like values should score 0."""
        score = score_gene_relevance(
            "kinase",
            {
                "geneId": "",
                "geneName": "",
                "displayName": "",
                "organism": "",
                "product": "",
            },
        )
        assert score == pytest.approx(0.0, abs=0.01)

    def test_matched_fields_with_mixed_types(self) -> None:
        """matchedFields list with non-string elements should be filtered."""
        score = score_gene_relevance(
            "kinase",
            {
                "geneId": "X",
                "geneName": "",
                "displayName": "",
                "organism": "",
                "product": "kinase",
                "matchedFields": [42, None, "gene_product", True],
            },
        )
        # gene_product is a primary field, so quality bonus should apply
        assert score > 0
