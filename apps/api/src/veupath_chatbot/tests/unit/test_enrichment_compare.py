"""Tests for cross-experiment enrichment comparison."""

from veupath_chatbot.services.enrichment.compare import (
    compare_enrichment_across,
)
from veupath_chatbot.services.experiment.types import (
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
)


def _cfg(name: str = "Test") -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmo",
        record_type="gene",
        search_name="GenesByText",
        parameters={},
        positive_controls=[],
        negative_controls=[],
        controls_search_name="",
        controls_param_name="",
        name=name,
    )


def _term(term_id: str, term_name: str, fold: float) -> EnrichmentTerm:
    return EnrichmentTerm(
        term_id=term_id,
        term_name=term_name,
        gene_count=10,
        background_count=100,
        fold_enrichment=fold,
        odds_ratio=1.0,
        p_value=0.01,
        fdr=0.05,
        bonferroni=0.1,
    )


def _exp_with_enrichment(
    exp_id: str,
    name: str,
    enrichment_results: list[EnrichmentResult],
) -> Experiment:
    e = Experiment(id=exp_id, config=_cfg(name))
    e.enrichment_results = enrichment_results
    return e


class TestCompareEnrichmentAcross:
    def test_basic_comparison(self) -> None:
        e1 = _exp_with_enrichment(
            "e1",
            "Alpha",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[_term("GO:001", "Transport", 3.5)],
                    total_genes_analyzed=100,
                )
            ],
        )
        e2 = _exp_with_enrichment(
            "e2",
            "Beta",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[_term("GO:001", "Transport", 2.0)],
                    total_genes_analyzed=80,
                )
            ],
        )
        result = compare_enrichment_across([e1, e2], ["e1", "e2"])

        assert result["experimentIds"] == ["e1", "e2"]
        assert result["experimentLabels"]["e1"] == "Alpha"
        assert result["experimentLabels"]["e2"] == "Beta"
        assert result["totalTerms"] == 1
        row = result["rows"][0]
        assert row["termKey"] == "go_process:GO:001"
        assert row["termName"] == "Transport"
        assert row["scores"]["e1"] == 3.5
        assert row["scores"]["e2"] == 2.0
        assert row["maxScore"] == 3.5
        assert row["experimentCount"] == 2

    def test_missing_term_in_one_experiment(self) -> None:
        e1 = _exp_with_enrichment(
            "e1",
            "Alpha",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[
                        _term("GO:001", "Transport", 3.0),
                        _term("GO:002", "Signaling", 1.5),
                    ],
                    total_genes_analyzed=100,
                )
            ],
        )
        e2 = _exp_with_enrichment(
            "e2",
            "Beta",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[_term("GO:001", "Transport", 2.0)],
                    total_genes_analyzed=80,
                )
            ],
        )
        result = compare_enrichment_across([e1, e2], ["e1", "e2"])

        assert result["totalTerms"] == 2
        rows_by_key = {r["termKey"]: r for r in result["rows"]}
        # GO:002 only in e1
        signaling = rows_by_key["go_process:GO:002"]
        assert signaling["scores"]["e1"] == 1.5
        assert signaling["scores"]["e2"] is None
        assert signaling["experimentCount"] == 1

    def test_filter_by_analysis_type(self) -> None:
        e1 = _exp_with_enrichment(
            "e1",
            "Alpha",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[_term("GO:001", "Transport", 3.0)],
                    total_genes_analyzed=100,
                ),
                EnrichmentResult(
                    analysis_type="pathway",
                    terms=[_term("PW:001", "MAPK", 2.0)],
                    total_genes_analyzed=100,
                ),
            ],
        )
        e2 = _exp_with_enrichment(
            "e2",
            "Beta",
            [
                EnrichmentResult(
                    analysis_type="pathway",
                    terms=[_term("PW:001", "MAPK", 4.0)],
                    total_genes_analyzed=80,
                )
            ],
        )
        result = compare_enrichment_across(
            [e1, e2], ["e1", "e2"], analysis_type="pathway"
        )

        assert result["totalTerms"] == 1
        assert result["rows"][0]["analysisType"] == "pathway"

    def test_sorted_by_max_score_descending(self) -> None:
        e1 = _exp_with_enrichment(
            "e1",
            "Alpha",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[
                        _term("GO:001", "Low", 1.0),
                        _term("GO:002", "High", 5.0),
                        _term("GO:003", "Mid", 3.0),
                    ],
                    total_genes_analyzed=100,
                )
            ],
        )
        result = compare_enrichment_across([e1], ["e1"])

        scores = [r["maxScore"] for r in result["rows"]]
        assert scores == sorted(scores, reverse=True)

    def test_empty_enrichment_results(self) -> None:
        e1 = _exp_with_enrichment("e1", "Alpha", [])
        e2 = _exp_with_enrichment("e2", "Beta", [])
        result = compare_enrichment_across([e1, e2], ["e1", "e2"])

        assert result["totalTerms"] == 0
        assert result["rows"] == []

    def test_multiple_analysis_types(self) -> None:
        e1 = _exp_with_enrichment(
            "e1",
            "Alpha",
            [
                EnrichmentResult(
                    analysis_type="go_process",
                    terms=[_term("GO:001", "Transport", 2.0)],
                    total_genes_analyzed=100,
                ),
                EnrichmentResult(
                    analysis_type="pathway",
                    terms=[_term("PW:001", "MAPK", 4.0)],
                    total_genes_analyzed=100,
                ),
            ],
        )
        result = compare_enrichment_across([e1], ["e1"])

        assert result["totalTerms"] == 2
        analysis_types = {r["analysisType"] for r in result["rows"]}
        assert "go_process" in analysis_types
        assert "pathway" in analysis_types

    def test_experiment_labels_fallback_to_id(self) -> None:
        cfg = _cfg(name="")
        e1 = Experiment(id="e1", config=cfg)
        e1.enrichment_results = []
        result = compare_enrichment_across([e1], ["e1"])
        assert result["experimentLabels"]["e1"] == "e1"
