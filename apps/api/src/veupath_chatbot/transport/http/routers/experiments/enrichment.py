"""Enrichment analysis endpoints for experiments."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.custom_enrichment import run_custom_enrichment
from veupath_chatbot.services.experiment.enrichment import upsert_enrichment_result
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.transport.http.deps import CurrentUser, ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import (
    CustomEnrichRequest,
    RunEnrichmentRequest,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{experiment_id}/enrich")
async def run_enrichment(
    exp: ExperimentDep,
    request: RunEnrichmentRequest,
    user_id: CurrentUser,
) -> list[JSONObject]:
    """Run enrichment analysis on an existing experiment's results."""
    from veupath_chatbot.services.experiment.types import to_json
    from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

    svc = EnrichmentService()
    results, errors = await svc.run_batch(
        site_id=exp.config.site_id,
        analysis_types=request.enrichment_types,
        step_id=exp.wdk_step_id,
        search_name=exp.config.search_name,
        record_type=exp.config.record_type,
        parameters=exp.config.parameters,
    )
    for r in results:
        upsert_enrichment_result(exp.enrichment_results, r)
    get_experiment_store().save(exp)

    if not results and errors:
        from veupath_chatbot.platform.errors import InternalError

        raise InternalError(
            title="Enrichment analysis failed",
            detail="; ".join(errors),
        )

    return [to_json(r) for r in results]


@router.post("/{experiment_id}/custom-enrich")
async def custom_enrichment(
    exp: ExperimentDep,
    request: CustomEnrichRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Test enrichment of a custom gene set against the experiment results."""
    return run_custom_enrichment(exp, request.gene_ids, request.gene_set_name)
