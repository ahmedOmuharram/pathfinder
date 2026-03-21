"""Gene set enrichment orchestration."""

from typing import cast

from redis.exceptions import RedisError

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import EnrichmentAnalysisType
from veupath_chatbot.services.export import get_export_service
from veupath_chatbot.services.gene_sets.types import GeneSet
from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

logger = get_logger(__name__)

_PVALUE_SIGNIFICANCE_THRESHOLD = 0.05


async def run_enrichment_for_gene_set(
    gene_set: GeneSet,
    analysis_types: list[EnrichmentAnalysisType],
) -> JSONObject:
    """Run enrichment analysis on a gene set and auto-export results.

    Orchestrates:
    1. EnrichmentService.run_batch() for ORA analysis
    2. Export service for CSV/TSV/JSON downloads

    Returns a summary dict with enrichment results, download links, and errors.
    """
    params: JSONObject | None = (
        {k: cast("JSONValue", v) for k, v in gene_set.parameters.items()}
        if gene_set.parameters is not None
        else None
    )

    svc = EnrichmentService()
    results, errors = await svc.run_batch(
        site_id=gene_set.site_id,
        analysis_types=analysis_types,
        step_id=gene_set.wdk_step_id,
        search_name=gene_set.search_name,
        record_type=gene_set.record_type or "transcript",
        parameters=params,
    )

    serialized = [r.model_dump(by_alias=True) for r in results]
    summary: JSONObject = {
        "analysisTypesRun": [r.get("analysisType", "unknown") for r in serialized],
        "totalSignificantTerms": sum(
            sum(
                1
                for t in r.get("terms", [])
                if isinstance(t, dict)
                and t.get("pValue", 1) < _PVALUE_SIGNIFICANCE_THRESHOLD
            )
            for r in serialized
        ),
    }

    if results:
        try:
            export_svc = get_export_service()
            name = gene_set.name or gene_set.id
            csv_result = await export_svc.export_enrichment(results, name)
            tsv_result = await export_svc.export_enrichment_tsv(results, name)
            json_result = await export_svc.export_enrichment_json(results, name)
            summary["downloads"] = {
                "csv": csv_result.url,
                "tsv": tsv_result.url,
                "json": json_result.url,
                "expiresInSeconds": csv_result.expires_in_seconds,
            }
        except (RedisError, OSError, ValueError, TypeError) as export_err:
            logger.warning("Enrichment export failed", error=str(export_err))

    summary["enrichmentResults"] = serialized
    if errors:
        summary["errors"] = cast("JSONValue", errors)

    return summary
