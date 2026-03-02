"""Enrichment analysis endpoints for experiments."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.custom_enrichment import run_custom_enrichment
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.transport.http.deps import ExperimentDep
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
) -> list[JSONObject]:
    """Run enrichment analysis on an existing experiment's results."""
    from veupath_chatbot.services.experiment.enrichment import (
        run_enrichment_analysis,
        run_enrichment_on_step,
    )
    from veupath_chatbot.services.experiment.types import enrichment_result_to_json

    use_step = exp.config.mode != "single" and exp.wdk_step_id is not None

    results: list[JSONObject] = []
    for enrich_type in request.enrichment_types:
        try:
            if use_step:
                er = await run_enrichment_on_step(
                    site_id=exp.config.site_id,
                    step_id=exp.wdk_step_id,
                    analysis_type=enrich_type,
                )
            else:
                er = await run_enrichment_analysis(
                    site_id=exp.config.site_id,
                    record_type=exp.config.record_type,
                    search_name=exp.config.search_name,
                    parameters=exp.config.parameters,
                    analysis_type=enrich_type,
                )
            exp.enrichment_results.append(er)
            results.append(enrichment_result_to_json(er))
        except Exception as exc:
            logger.warning(
                "Enrichment analysis failed",
                analysis_type=enrich_type,
                error=str(exc),
            )

    get_experiment_store().save(exp)
    return results


@router.post("/{experiment_id}/custom-enrich")
async def custom_enrichment(
    exp: ExperimentDep,
    request: CustomEnrichRequest,
) -> JSONObject:
    """Test enrichment of a custom gene set against the experiment results."""
    return run_custom_enrichment(exp, request.gene_ids, request.gene_set_name)
