"""Cross-experiment comparison endpoints: overlap and enrichment comparison."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.enrichment_compare import (
    compare_enrichment_across,
)
from veupath_chatbot.services.experiment.overlap import compute_gene_set_overlap
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment
from veupath_chatbot.transport.http.schemas.experiments import (
    EnrichmentCompareRequest,
    OverlapRequest,
)

router = APIRouter()


@router.post("/overlap")
async def compute_overlap(body: OverlapRequest) -> JSONObject:
    """Compute pairwise gene set overlap between experiments."""
    store = get_experiment_store()
    experiments: list[Experiment] = []
    for eid in body.experiment_ids:
        exp = await store.aget(eid)
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        experiments.append(exp)

    return compute_gene_set_overlap(experiments, body.experiment_ids)


@router.post("/enrichment-compare")
async def compare_enrichment(body: EnrichmentCompareRequest) -> JSONObject:
    """Compare enrichment results across experiments."""
    store = get_experiment_store()
    experiments: list[Experiment] = []
    for eid in body.experiment_ids:
        exp = await store.aget(eid)
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        experiments.append(exp)

    return compare_enrichment_across(
        experiments, body.experiment_ids, body.analysis_type
    )
