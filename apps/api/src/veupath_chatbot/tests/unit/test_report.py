"""Tests for HTML report generation."""

from veupath_chatbot.services.experiment.report import (
    _esc,
    _num,
    _pct,
    generate_experiment_report,
)
from veupath_chatbot.services.experiment.types import (
    BootstrapResult,
    ConfidenceInterval,
    ConfusionMatrix,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    GeneInfo,
    RankMetrics,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)


def _cfg(name: str = "Test Experiment") -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmo",
        record_type="gene",
        search_name="GenesByText",
        parameters={"text": "kinase"},
        positive_controls=["g1", "g2"],
        negative_controls=["n1"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
        name=name,
    )


def _minimal_experiment(name: str = "Test Experiment") -> Experiment:
    return Experiment(
        id="exp-001",
        config=_cfg(name),
        created_at="2025-01-01T00:00:00",
    )


class TestHelpers:
    def test_esc_html_entities(self) -> None:
        assert _esc("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_esc_ampersand(self) -> None:
        assert _esc("A & B") == "A &amp; B"

    def test_pct(self) -> None:
        assert _pct(0.8) == "80.0%"
        assert _pct(1.0) == "100.0%"
        assert _pct(0.0) == "0.0%"

    def test_num(self) -> None:
        assert _num(0.12345) == "0.1235"
        assert _num(1.0) == "1.0000"


class TestGenerateReport:
    def test_minimal_report_structure(self) -> None:
        exp = _minimal_experiment()
        html = generate_experiment_report(exp)

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "Test Experiment" in html
        assert "exp-001" in html

    def test_config_section(self) -> None:
        exp = _minimal_experiment()
        html = generate_experiment_report(exp)

        assert "Configuration" in html
        assert "GenesByText" in html
        assert "2" in html  # positive controls count
        assert "1" in html  # negative controls count

    def test_report_escapes_html(self) -> None:
        exp = _minimal_experiment(name="<script>alert</script>")
        html = generate_experiment_report(exp)

        assert "<script>alert</script>" not in html
        assert "&lt;script&gt;" in html

    def test_rank_metrics_section(self) -> None:
        exp = _minimal_experiment()
        exp.rank_metrics = RankMetrics(
            precision_at_k={50: 0.6},
            recall_at_k={50: 0.4},
            enrichment_at_k={50: 2.0},
            total_results=200,
        )
        html = generate_experiment_report(exp)

        assert "Rank-Based Metrics" in html
        assert "Precision@50" in html
        assert "60.0%" in html

    def test_classification_section(self) -> None:
        exp = _minimal_experiment()
        exp.metrics = ExperimentMetrics(
            confusion_matrix=ConfusionMatrix(
                true_positives=8,
                false_positives=2,
                true_negatives=18,
                false_negatives=2,
            ),
            sensitivity=0.8,
            specificity=0.9,
            precision=0.8,
            f1_score=0.8,
            mcc=0.7,
            balanced_accuracy=0.85,
        )
        html = generate_experiment_report(exp)

        assert "Classification Metrics" in html
        assert "Confusion Matrix" in html
        assert "80.0%" in html  # sensitivity
        assert "Sensitivity" in html
        assert "Specificity" in html

    def test_robustness_section(self) -> None:
        exp = _minimal_experiment()
        exp.robustness = BootstrapResult(
            n_iterations=200,
            metric_cis={
                "sensitivity": ConfidenceInterval(
                    lower=0.7, mean=0.8, upper=0.9, std=0.05
                ),
            },
            rank_metric_cis={},
            top_k_stability=0.85,
        )
        html = generate_experiment_report(exp)

        assert "Robustness" in html
        assert "200 bootstrap iterations" in html
        assert "sensitivity" in html

    def test_step_analysis_section(self) -> None:
        exp = _minimal_experiment()
        exp.step_analysis = StepAnalysisResult(
            step_evaluations=[
                StepEvaluation(
                    step_id="s1",
                    search_name="GenesByText",
                    display_name="Text Search",
                    estimated_size=100,
                    positive_hits=8,
                    positive_total=10,
                    negative_hits=2,
                    negative_total=20,
                    recall=0.8,
                    false_positive_rate=0.1,
                ),
            ],
            step_contributions=[
                StepContribution(
                    step_id="s1",
                    search_name="GenesByText",
                    baseline_recall=0.8,
                    ablated_recall=0.3,
                    recall_delta=-0.5,
                    baseline_fpr=0.1,
                    ablated_fpr=0.05,
                    fpr_delta=-0.05,
                    verdict="essential",
                    narrative="This step contributes significantly.",
                ),
            ],
        )
        html = generate_experiment_report(exp)

        assert "Step Analysis" in html
        assert "Text Search" in html
        assert "essential" in html

    def test_enrichment_section(self) -> None:
        exp = _minimal_experiment()
        exp.enrichment_results = [
            EnrichmentResult(
                analysis_type="go_process",
                terms=[
                    EnrichmentTerm(
                        term_id="GO:001",
                        term_name="DNA replication",
                        gene_count=5,
                        background_count=100,
                        fold_enrichment=3.5,
                        odds_ratio=2.0,
                        p_value=0.001,
                        fdr=0.01,
                        bonferroni=0.05,
                    ),
                ],
                total_genes_analyzed=50,
            ),
        ]
        html = generate_experiment_report(exp)

        assert "Enrichment Analysis" in html
        assert "DNA replication" in html
        assert "go_process" in html

    def test_gene_lists_section(self) -> None:
        exp = _minimal_experiment()
        exp.true_positive_genes = [GeneInfo(id="g1"), GeneInfo(id="g2")]
        exp.false_negative_genes = [GeneInfo(id="g3")]
        exp.false_positive_genes = [GeneInfo(id="n1")]
        html = generate_experiment_report(exp)

        assert "Gene Lists" in html
        assert "True Positives (2)" in html
        assert "False Negatives (1)" in html
        assert "False Positives (1)" in html

    def test_footer(self) -> None:
        exp = _minimal_experiment()
        html = generate_experiment_report(exp)

        assert "Pathfinder Experiment Lab" in html
        assert "exp-001" in html

    def test_total_time_shown(self) -> None:
        exp = _minimal_experiment()
        exp.total_time_seconds = 12.3
        html = generate_experiment_report(exp)
        assert "12.3s" in html

    def test_control_set_id_shown(self) -> None:
        exp = _minimal_experiment()
        exp.config.control_set_id = "cs-apicoplast"
        html = generate_experiment_report(exp)
        assert "cs-apicoplast" in html
