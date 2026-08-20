"""The HTML report renders an enrichment term whose values are not finite."""

from __future__ import annotations

from pathfinder.services.enrichment.types import EnrichmentResult, EnrichmentTerm
from pathfinder.services.experiment.report import generate_experiment_report
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)


def _term(**overrides: object) -> EnrichmentTerm:
    fields: dict[str, object] = {
        "term_id": "GO:0004672",
        "term_name": "protein kinase activity",
        "gene_count": 3,
        "background_count": 120,
        "fold_enrichment": 3.48,
        "odds_ratio": 4.12,
        "p_value": 0.0001,
        "fdr": 0.002,
        "bonferroni": 0.005,
        "genes": [],
    }
    fields.update(overrides)
    return EnrichmentTerm.model_validate(fields)


def _experiment(terms: list[EnrichmentTerm]) -> Experiment:
    return Experiment(
        id="exp-report",
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            name="kinase panel",
        ),
        status="completed",
        enrichment_results=[EnrichmentResult(analysis_type="go_function", terms=terms)],
    )


def test_a_finite_term_keeps_its_formatted_numbers() -> None:
    html = generate_experiment_report(_experiment([_term()]))

    assert "<td class='numeric'>3.48</td>" in html
    assert "<td class='numeric'>2.00e-03</td>" in html


def test_an_unbounded_fold_enrichment_renders_as_inf() -> None:
    term = _term(fold_enrichment="Infinity", fdr="NaN")

    html = generate_experiment_report(_experiment([term]))

    assert "<td class='numeric'>Inf</td>" in html
    assert "<td class='numeric'>n/a</td>" in html
