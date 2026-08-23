"""Scored variant comparison (Phase 2b): run a full experiment per variant
against positive/negative control gene lists, then rank the variants by an
objective metric (MCC by default) and name a winner.

This is the controls-based counterpart to the no-controls exploratory
``variant_comparison`` — here every variant gets real classification metrics
(sensitivity, precision, MCC, ...) so there's an objective "best".
"""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel

from pathfinder.platform.errors import WDKError
from pathfinder.services.experiment.service import run_experiment
from pathfinder.services.experiment.types.experiment import ExperimentConfig
from pathfinder.services.experiment.variant_comparison import VariantSpec

CONTROLS_SEARCH_NAME = "GeneByLocusTag"
CONTROLS_PARAM_NAME = "ds_gene_ids"

# objective name -> ScoredVariant attribute to rank on
_RANK_ATTR: dict[str, str] = {
    "mcc": "mcc",
    "balanced_accuracy": "balanced_accuracy",
    "f1": "f1",
    "precision": "precision",
    "sensitivity": "sensitivity",
}


class ScoredVariant(CamelModel):
    label: str
    search_name: str
    experiment_id: str | None = None
    mcc: float | None = None
    balanced_accuracy: float | None = None
    f1: float | None = None
    sensitivity: float | None = None
    precision: float | None = None
    error: str | None = None


class ScoredComparison(CamelModel):
    variants: list[ScoredVariant]
    winner_label: str | None
    objective: str


async def _score_one(
    spec: VariantSpec,
    *,
    site_id: str,
    user_id: str | None,
    positive_controls: list[str],
    negative_controls: list[str],
) -> ScoredVariant:
    config = ExperimentConfig(
        site_id=site_id,
        record_type=spec.record_type,
        search_name=spec.search_name,
        parameters=spec.parameters,
        positive_controls=positive_controls,
        negative_controls=negative_controls,
        controls_search_name=CONTROLS_SEARCH_NAME,
        controls_param_name=CONTROLS_PARAM_NAME,
        name=spec.label,
    )
    try:
        exp = await run_experiment(config, user_id=user_id)
    except (WDKError, ValueError) as exc:
        return ScoredVariant(
            label=spec.label, search_name=spec.search_name, error=str(exc)
        )
    if exp.status == "error" or exp.metrics is None:
        return ScoredVariant(
            label=spec.label,
            search_name=spec.search_name,
            experiment_id=exp.id,
            error=exp.error or "experiment produced no metrics",
        )
    m = exp.metrics
    return ScoredVariant(
        label=spec.label,
        search_name=spec.search_name,
        experiment_id=exp.id,
        mcc=m.mcc,
        balanced_accuracy=m.balanced_accuracy,
        f1=m.f1_score,
        sensitivity=m.sensitivity,
        precision=m.precision,
    )


async def run_scored_comparison(
    site_id: str,
    user_id: str | None,
    variants: list[VariantSpec],
    *,
    positive_controls: list[str],
    negative_controls: list[str],
    objective: str = "mcc",
) -> ScoredComparison:
    """Run each variant as a scored experiment and rank by *objective*.

    Variants run sequentially (each is a full WDK experiment). Failed
    variants are reported with an error and excluded from ranking.
    """
    rank_attr = _RANK_ATTR.get(objective, "mcc")
    scored = [
        await _score_one(
            v,
            site_id=site_id,
            user_id=user_id,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )
        for v in variants
    ]
    ok = [s for s in scored if s.error is None and getattr(s, rank_attr) is not None]
    winner = max(ok, key=lambda s: getattr(s, rank_attr)) if ok else None
    return ScoredComparison(
        variants=scored,
        winner_label=winner.label if winner else None,
        objective=objective,
    )
