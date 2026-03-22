"""Tests for services.gene_lookup.scoring -- gene relevance scoring."""

import pytest

from veupath_chatbot.services.gene_lookup.result import GeneResult
from veupath_chatbot.services.gene_lookup.scoring import (
    _EXACT_BONUS,
    _W_DISPLAY_NAME,
    _W_FIELD_QUALITY,
    _W_GENE_ID,
    _W_GENE_NAME,
    _W_ORGANISM,
    _W_PRODUCT,
    score_gene_relevance,
)


class TestScoreGeneRelevance:
    """Tests for the additive gene relevance scorer."""

    def test_exact_gene_id_match_scores_highest_component(self) -> None:
        """When the query exactly matches geneId, the gene ID component should dominate."""
        score = score_gene_relevance(
            "PF3D7_0100100",
            GeneResult(gene_id="PF3D7_0100100"),
        )
        # Gene ID exact match contributes _W_GENE_ID * 1.0 = 100
        assert score >= _W_GENE_ID * 0.9

    def test_exact_product_match_gets_bonus(self) -> None:
        """When product exactly matches query, the exact bonus should fire."""
        score = score_gene_relevance(
            "alpha tubulin 2",
            GeneResult(
                gene_id="PF3D7_0422300",
                display_name="alpha tubulin 2",
                product="alpha tubulin 2",
            ),
        )
        # product and displayName exact match => _EXACT_BONUS
        assert score >= _EXACT_BONUS * 0.9

    def test_partial_product_match_no_bonus(self) -> None:
        """A partial match shouldn't get the exact bonus."""
        score = score_gene_relevance(
            "alpha tubulin 2",
            GeneResult(
                gene_id="PF3D7_XXXX",
                display_name="casein kinase 2, alpha subunit",
                product="casein kinase 2, alpha subunit",
            ),
        )
        # The partial match score should be lower than a perfect match
        perfect_score = score_gene_relevance(
            "alpha tubulin 2",
            GeneResult(
                gene_id="PF3D7_0422300",
                gene_name="alpha tubulin 2",
                display_name="alpha tubulin 2",
                product="alpha tubulin 2",
            ),
        )
        assert score < perfect_score

    def test_organism_match_adds_score(self) -> None:
        """When query matches one organism but not another, the matched one scores higher."""
        score_with_org = score_gene_relevance(
            "Plasmodium falciparum 3D7",
            GeneResult(
                gene_id="PF3D7_0100100",
                organism="Plasmodium falciparum 3D7",
            ),
        )
        score_without_org = score_gene_relevance(
            "Plasmodium falciparum 3D7",
            GeneResult(
                gene_id="PF3D7_0100100",
                organism="Toxoplasma gondii ME49",
            ),
        )
        assert score_with_org > score_without_org

    def test_matched_fields_primary_quality_bonus(self) -> None:
        """Primary field matches add positive quality weight."""
        score_primary = score_gene_relevance(
            "kinase",
            GeneResult(
                gene_id="X",
                product="kinase",
                matched_fields=["gene_product"],
            ),
        )
        score_secondary = score_gene_relevance(
            "kinase",
            GeneResult(
                gene_id="X",
                product="kinase",
                matched_fields=["gene_PubMed"],
            ),
        )
        assert score_primary > score_secondary

    def test_empty_result_scores_zero(self) -> None:
        score = score_gene_relevance("anything", GeneResult(gene_id=""))
        assert score == pytest.approx(0.0)

    def test_empty_query_scores_zero(self) -> None:
        score = score_gene_relevance(
            "",
            GeneResult(
                gene_id="PF3D7_0100100",
                gene_name="CSP",
                display_name="CSP",
                organism="Plasmodium falciparum 3D7",
                product="circumsporozoite protein",
            ),
        )
        assert score == pytest.approx(0.0)

    def test_matched_fields_none_treated_as_empty(self) -> None:
        """If matchedFields is None, it should be treated as empty."""
        score = score_gene_relevance(
            "kinase",
            GeneResult(
                gene_id="X",
                product="kinase",
                matched_fields=None,
            ),
        )
        # Should not crash, just no field quality contribution
        assert score >= 0.0

    def test_gene_name_exact_match_triggers_bonus(self) -> None:
        """When geneName exactly matches, the best_desc check fires."""
        score = score_gene_relevance(
            "CSP",
            GeneResult(
                gene_id="PF3D7_0304600",
                gene_name="CSP",
                display_name="CSP",
            ),
        )
        # name_score = 1.0 => best_desc >= 0.95 => bonus fires
        assert score >= _W_GENE_NAME + _EXACT_BONUS * 0.9

    def test_weights_are_positive(self) -> None:
        """Sanity check that all weights are positive."""
        assert _W_GENE_ID > 0
        assert _W_GENE_NAME > 0
        assert _W_ORGANISM > 0
        assert _W_PRODUCT > 0
        assert _W_DISPLAY_NAME > 0
        assert _W_FIELD_QUALITY > 0
        assert _EXACT_BONUS > 0
