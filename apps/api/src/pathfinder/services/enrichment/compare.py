"""Cross-experiment enrichment comparison."""

from typing import TypedDict

from pydantic import JsonValue

from pathfinder.services.enrichment.ranking import (
    best_ratio,
    ratio_cell,
    ratio_sort_key,
)
from pathfinder.services.experiment.types import Experiment


class EnrichmentRow(TypedDict):
    """Shape of one term row in the enrichment comparison.

    A score is a number, the unbounded token, or null when the experiment has
    no such term.
    """

    termKey: str
    termName: str
    analysisType: str
    scores: dict[str, JsonValue]
    maxScore: float | str
    experimentCount: int


class EnrichmentCompareResult(TypedDict):
    """Return shape of :func:`compare_enrichment_across`."""

    experimentIds: list[str]
    experimentLabels: dict[str, str]
    rows: list[EnrichmentRow]
    totalTerms: int


def compare_enrichment_across(
    experiments: list[Experiment],
    experiment_ids: list[str],
    analysis_type: str | None = None,
) -> EnrichmentCompareResult:
    """Compare enrichment results across experiments.

    Builds a term-by-experiment matrix of fold-enrichment scores.
    Optionally filters to a single analysis type.
    """
    labels: dict[str, str] = {
        exp.id: (exp.config.name or exp.id) for exp in experiments
    }

    # Collect scores: term_key -> { experiment_id -> fold_enrichment }
    # Also track term metadata (name, analysis type)
    term_scores: dict[str, dict[str, float | None]] = {}
    term_meta: dict[str, tuple[str, str]] = {}

    for exp in experiments:
        for er in exp.enrichment_results:
            if analysis_type and er.analysis_type != analysis_type:
                continue
            for term in er.terms:
                key = f"{er.analysis_type}:{term.term_id}"
                if key not in term_meta:
                    term_meta[key] = (term.term_name, er.analysis_type)
                    term_scores[key] = {}
                term_scores[key][exp.id] = term.fold_enrichment

    # Build rows sorted by best score, unbounded first
    best: dict[str, float | None] = {
        key: best_ratio(scores.values()) for key, scores in term_scores.items()
    }
    rows: list[EnrichmentRow] = []
    for key in sorted(term_scores, key=lambda k: ratio_sort_key(best[k])):
        name, a_type = term_meta[key]
        scores_map = term_scores[key]
        scores_for_row: dict[str, JsonValue] = {
            eid: ratio_cell(scores_map[eid]) if eid in scores_map else None
            for eid in experiment_ids
        }
        rows.append(
            {
                "termKey": key,
                "termName": name,
                "analysisType": a_type,
                "scores": scores_for_row,
                "maxScore": ratio_cell(best[key]),
                "experimentCount": len(scores_map),
            }
        )

    return {
        "experimentIds": list(experiment_ids),
        "experimentLabels": labels,
        "rows": rows,
        "totalTerms": len(rows),
    }
