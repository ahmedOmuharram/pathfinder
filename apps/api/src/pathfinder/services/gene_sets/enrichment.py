"""Gene set enrichment orchestration."""

from typing import cast

from pydantic import JsonValue

from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.enrichment.service import EnrichmentService
from pathfinder.services.enrichment.types import EnrichmentAnalysisType
from pathfinder.services.export import get_export_service
from pathfinder.services.gene_sets.types import GeneSet

logger = get_logger(__name__)

_FDR_SIGNIFICANCE_THRESHOLD = 0.05


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
    svc = EnrichmentService()
    results, errors = await svc.run_batch(
        site_id=gene_set.site_id,
        analysis_types=analysis_types,
        step_id=gene_set.wdk_step_id,
        search_name=gene_set.search_name,
        record_type=gene_set.record_type or "transcript",
        parameters=gene_set.parameters,
    )

    serialized = [r.model_dump(by_alias=True) for r in results]
    summary: JSONObject = {
        "analysisTypesRun": [r.analysis_type for r in results],
        "totalSignificantTerms": sum(
            1 for r in results for t in r.terms if t.fdr < _FDR_SIGNIFICANCE_THRESHOLD
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
        except (OSError, ValueError, TypeError) as export_err:
            logger.warning("Enrichment export failed", error=str(export_err))

    summary["enrichmentResults"] = cast("JsonValue", serialized)
    if errors:
        summary["errors"] = cast("JsonValue", errors)

    return summary
