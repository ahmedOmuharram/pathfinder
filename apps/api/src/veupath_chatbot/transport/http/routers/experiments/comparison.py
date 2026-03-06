"""Cross-experiment comparison endpoints: overlap and enrichment comparison."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.errors import ForbiddenError, NotFoundError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.enrichment_compare import (
    compare_enrichment_across,
)
from veupath_chatbot.services.experiment.overlap import compute_gene_set_overlap
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment
from veupath_chatbot.transport.http.deps import CurrentUser
from veupath_chatbot.transport.http.schemas.experiments import (
    EnrichmentCompareRequest,
    OverlapRequest,
)

router = APIRouter()


async def _get_owned_experiments(
    experiment_ids: list[str], user_id: str
) -> list[Experiment]:
    """Fetch experiments by IDs and verify ownership."""
    store = get_experiment_store()
    experiments: list[Experiment] = []
    for eid in experiment_ids:
        exp = await store.aget(eid)
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        if exp.user_id is not None and exp.user_id != user_id:
            raise ForbiddenError(title="Not authorized to access this experiment")
        experiments.append(exp)
    return experiments


@router.post("/overlap")
async def compute_overlap(body: OverlapRequest, user_id: CurrentUser) -> JSONObject:
    """Compute pairwise gene set overlap between experiments."""
    experiments = await _get_owned_experiments(body.experiment_ids, str(user_id))
    return compute_gene_set_overlap(experiments, body.experiment_ids)


@router.post("/enrichment-compare")
async def compare_enrichment(
    body: EnrichmentCompareRequest, user_id: CurrentUser
) -> JSONObject:
    """Compare enrichment results across experiments."""
    experiments = await _get_owned_experiments(body.experiment_ids, str(user_id))
    return compare_enrichment_across(
        experiments, body.experiment_ids, body.analysis_type
    )
