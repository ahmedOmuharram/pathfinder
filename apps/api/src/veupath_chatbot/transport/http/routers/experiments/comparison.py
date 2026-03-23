"""Cross-experiment comparison endpoints: overlap and enrichment comparison."""

from fastapi import APIRouter

from veupath_chatbot.services.enrichment.compare import (
    EnrichmentCompareResult,
    compare_enrichment_across,
)
from veupath_chatbot.services.experiment.overlap import (
    OverlapResult,
    compute_gene_set_overlap,
)
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    get_experiments_owned_by_user,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    EnrichmentCompareRequest,
    OverlapRequest,
)

router = APIRouter()


@router.post("/overlap")
async def compute_overlap(body: OverlapRequest, user_id: CurrentUser) -> OverlapResult:
    """Compute pairwise gene set overlap between experiments."""
    experiments = await get_experiments_owned_by_user(body.experiment_ids, str(user_id))
    return compute_gene_set_overlap(experiments, body.experiment_ids)


@router.post("/enrichment-compare")
async def compare_enrichment(
    body: EnrichmentCompareRequest, user_id: CurrentUser
) -> EnrichmentCompareResult:
    """Compare enrichment results across experiments."""
    experiments = await get_experiments_owned_by_user(body.experiment_ids, str(user_id))
    return compare_enrichment_across(
        experiments, body.experiment_ids, body.analysis_type
    )
