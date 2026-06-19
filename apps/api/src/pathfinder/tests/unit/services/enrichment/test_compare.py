"""compare_enrichment_across — the cross-gene-set scoring the workbench
'score genes across two sets' flow uses. Builds a term-by-experiment
fold-enrichment matrix; we assert the real matrix for two experiments that
share one GO term and each have a distinct one.
"""

from __future__ import annotations

from pathfinder.services.enrichment.compare import compare_enrichment_across
from pathfinder.services.enrichment.types import EnrichmentResult, EnrichmentTerm
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)


def _term(term_id: str, name: str, fold: float) -> EnrichmentTerm:
    return EnrichmentTerm.model_validate(
        {
            "term_id": term_id,
            "term_name": name,
            "gene_count": 5,
            "background_count": 100,
            "fold_enrichment": fold,
            "odds_ratio": fold,
            "p_value": 0.001,
            "fdr": 0.01,
            "bonferroni": 0.02,
            "genes": [],
        }
    )


def _exp(exp_id: str, name: str, terms: list[EnrichmentTerm]) -> Experiment:
    return Experiment(
        id=exp_id,
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            name=name,
        ),
        status="completed",
        enrichment_results=[EnrichmentResult(analysis_type="go_process", terms=terms)],
    )


def _experiments() -> list[Experiment]:
    return [
        _exp(
            "exp-kinases",
            "Kinases",
            [
                _term("GO:0004672", "protein kinase activity", 5.0),
                _term("GO:0006468", "protein phosphorylation", 3.0),
            ],
        ),
        _exp(
            "exp-phosphatases",
            "Phosphatases",
            [
                _term("GO:0004672", "protein kinase activity", 2.0),
                _term("GO:0016311", "dephosphorylation", 4.0),
            ],
        ),
    ]


def test_shared_term_carries_both_scores_and_count_two() -> None:
    result = compare_enrichment_across(
        _experiments(), ["exp-kinases", "exp-phosphatases"]
    )
    shared = next(r for r in result["rows"] if r["termKey"] == "go_process:GO:0004672")
    assert shared["termName"] == "protein kinase activity"
    assert shared["experimentCount"] == 2
    assert shared["scores"] == {"exp-kinases": 5.0, "exp-phosphatases": 2.0}
    assert shared["maxScore"] == 5.0


def test_rows_sorted_by_max_score_descending() -> None:
    result = compare_enrichment_across(
        _experiments(), ["exp-kinases", "exp-phosphatases"]
    )
    assert [r["maxScore"] for r in result["rows"]] == [5.0, 4.0, 3.0]
    assert result["totalTerms"] == 3
    assert result["experimentLabels"] == {
        "exp-kinases": "Kinases",
        "exp-phosphatases": "Phosphatases",
    }


def test_distinct_term_has_null_for_the_other_experiment() -> None:
    result = compare_enrichment_across(
        _experiments(), ["exp-kinases", "exp-phosphatases"]
    )
    kinase_only = next(
        r for r in result["rows"] if r["termKey"] == "go_process:GO:0006468"
    )
    assert kinase_only["experimentCount"] == 1
    assert kinase_only["scores"] == {"exp-kinases": 3.0, "exp-phosphatases": None}


def test_analysis_type_filter_excludes_non_matching_terms() -> None:
    # The experiments only have go_process terms; filtering to pathway is empty.
    result = compare_enrichment_across(
        _experiments(), ["exp-kinases", "exp-phosphatases"], analysis_type="pathway"
    )
    assert result["rows"] == []
    assert result["totalTerms"] == 0
