"""Cross-experiment enrichment comparison."""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import Experiment


def compare_enrichment_across(
    experiments: list[Experiment],
    experiment_ids: list[str],
    analysis_type: str | None = None,
) -> JSONObject:
    """Compare enrichment results across experiments.

    Builds a term-by-experiment matrix of fold-enrichment scores.
    Optionally filters to a single analysis type.
    """
    labels: dict[str, str] = {
        exp.id: (exp.config.name or exp.id) for exp in experiments
    }

    # Collect scores: term_key -> { experiment_id -> fold_enrichment }
    # Also track term metadata (name, analysis type)
    term_scores: dict[str, dict[str, float]] = {}
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

    # Build rows sorted by max score descending
    rows: list[JSONObject] = []
    for key in sorted(
        term_scores,
        key=lambda k: max(term_scores[k].values()) if term_scores[k] else 0.0,
        reverse=True,
    ):
        name, a_type = term_meta[key]
        scores_map = term_scores[key]
        scores_for_row: dict[str, JSONValue] = {
            eid: round(scores_map[eid], 4) if eid in scores_map else None
            for eid in experiment_ids
        }
        max_score = max(scores_map.values()) if scores_map else 0.0
        rows.append(
            {
                "termKey": key,
                "termName": name,
                "analysisType": a_type,
                "scores": scores_for_row,
                "maxScore": round(max_score, 4),
                "experimentCount": len(scores_map),
            }
        )

    return {
        "experimentIds": list(experiment_ids),
        "experimentLabels": labels,
        "rows": rows,
        "totalTerms": len(rows),
    }
