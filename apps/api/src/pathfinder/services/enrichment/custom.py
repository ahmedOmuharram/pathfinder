"""Custom gene set enrichment analysis against experiment results."""

import math
from typing import TypedDict

from pathfinder.services.enrichment.stats import hypergeometric_log_sf
from pathfinder.services.experiment.types import Experiment


class CustomEnrichmentResult(TypedDict):
    """Return shape of :func:`run_custom_enrichment`."""

    geneSetName: str
    geneSetSize: int
    overlapCount: int
    overlapGenes: list[str]
    backgroundSize: int
    tpCount: int
    foldEnrichment: float
    pValue: float
    oddsRatio: float


def run_custom_enrichment(
    exp: Experiment,
    gene_ids: list[str],
    gene_set_name: str,
) -> CustomEnrichmentResult:
    """Test enrichment of a custom gene set against the experiment results.

    Overlap, fold enrichment, hypergeometric p-value and odds ratio come from
    the pasted genes inside the background: a gene outside it is not a draw.
    """
    result_ids = exp.result_gene_ids()
    tp_ids, _, fn_ids, tn_ids = exp.classification_id_sets()
    gene_set = set(gene_ids)
    universe = result_ids | fn_ids | tn_ids
    gene_set_in_universe = gene_set & universe
    overlap = result_ids & gene_set
    tp_in_overlap = tp_ids & gene_set

    background = len(result_ids) + len(fn_ids) + len(tn_ids)
    background = max(background, 1)
    result_size = max(len(result_ids), 1)
    in_universe_size = len(gene_set_in_universe)

    expected = result_size * in_universe_size / background
    fold = len(overlap) / expected if expected > 0 else 0.0

    a = len(overlap)  # in result AND in the in-universe gene set
    b = in_universe_size - a  # in the in-universe gene set but NOT in result
    c = result_size - a  # in result but NOT in the in-universe gene set
    d = max(background - a - b - c, 0)  # in neither
    odds = (a * max(d, 1)) / (max(b, 1) * max(c, 1))

    log_p = hypergeometric_log_sf(
        len(overlap), background, result_size, in_universe_size
    )
    p_value = math.exp(log_p)

    return {
        "geneSetName": gene_set_name,
        "geneSetSize": len(gene_set),
        "overlapCount": len(overlap),
        "overlapGenes": sorted(overlap),
        "backgroundSize": background,
        "tpCount": len(tp_in_overlap),
        "foldEnrichment": round(fold, 4),
        "pValue": p_value,
        "oddsRatio": round(odds, 4),
    }
