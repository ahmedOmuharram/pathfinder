"""Gene set enrichment orchestration.

Two entry points share one WDK path: a stored gene set, and a gene list given
by value.
"""

from collections.abc import Mapping
from typing import cast

from assistant_core.platform.logging import get_logger
from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKEnrichmentResponse,
    WDKEnrichmentRowBase,
    WDKGoEnrichmentRow,
    WDKPathwayEnrichmentRow,
    WDKWordEnrichmentRow,
)
from pathfinder.platform.errors import InternalError, ValidationError
from pathfinder.services.enrichment.service import EnrichmentService
from pathfinder.services.enrichment.types import (
    ALL_ENRICHMENT_ANALYSIS_TYPES,
    BackgroundSource,
    EnrichmentAnalysisType,
    EnrichmentTerm,
)
from pathfinder.services.export import get_export_service
from pathfinder.services.gene_sets.types import GeneSet
from pathfinder.services.gene_sets.wdk_helpers import (
    build_enrichment_params_from_gene_ids,
)

logger = get_logger(__name__)

_FDR_SIGNIFICANCE_THRESHOLD = 0.05

MAX_ENRICHMENT_GENE_IDS = 200
"""The largest gene list one enrichment call accepts."""


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
            1
            for r in results
            for t in r.terms
            if t.fdr is not None and t.fdr < _FDR_SIGNIFICANCE_THRESHOLD
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


def _wire_key(model: type[BaseModel], field_name: str) -> str:
    """The JSON key a WDK model field is read from."""
    alias = model.model_fields[field_name].alias
    if alias is None:
        msg = f"{model.__name__}.{field_name} carries no WDK wire key"
        raise TypeError(msg)
    return alias


class EnrichmentSourceColumns(CamelModel):
    """The WDK keys an analysis type's identity fields come from.

    The enrichment plugins name their own columns and a wrong name yields an
    empty column rather than an error, so each analysis reports the two it read.
    """

    model_config = ConfigDict(frozen=True)

    envelope: str
    term_id: str
    term_name: str


def _columns(
    row_model: type[WDKEnrichmentRowBase],
    term_id_field: str,
    term_name_field: str,
) -> EnrichmentSourceColumns:
    return EnrichmentSourceColumns(
        envelope=_wire_key(WDKEnrichmentResponse, "result_data"),
        term_id=_wire_key(row_model, term_id_field),
        term_name=_wire_key(row_model, term_name_field),
    )


SOURCE_COLUMNS: Mapping[EnrichmentAnalysisType, EnrichmentSourceColumns] = {
    "go_function": _columns(WDKGoEnrichmentRow, "go_id", "go_term"),
    "go_component": _columns(WDKGoEnrichmentRow, "go_id", "go_term"),
    "go_process": _columns(WDKGoEnrichmentRow, "go_id", "go_term"),
    "pathway": _columns(WDKPathwayEnrichmentRow, "pathway_id", "pathway_name"),
    "word": _columns(WDKWordEnrichmentRow, "word", "pathway_name"),
}


class EnrichedAnalysis(CamelModel):
    """One analysis type's terms, and the columns they were read from."""

    model_config = ConfigDict(frozen=True)

    analysis_type: EnrichmentAnalysisType
    source_columns: EnrichmentSourceColumns
    terms: list[EnrichmentTerm] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def _columns_belong_to_the_analysis(self) -> "EnrichedAnalysis":
        expected = SOURCE_COLUMNS[self.analysis_type]
        if self.source_columns != expected:
            msg = f"{self.analysis_type} is read through {expected}"
            raise ValueError(msg)
        return self


class GeneIdEnrichment(CamelModel):
    """Over-representation results for a gene list given by value."""

    model_config = ConfigDict(frozen=True)

    site_id: str
    gene_count: int
    background: BackgroundSource
    analyses: list[EnrichedAnalysis]


def _clean_gene_ids(gene_ids: list[str]) -> list[str]:
    """Trim, drop blanks and repeats, and refuse a list out of bounds."""
    ids = list(dict.fromkeys(gid.strip() for gid in gene_ids if gid.strip()))
    if not ids:
        msg = "gene_ids holds no gene identifier."
        raise ValidationError(detail=msg)
    if len(ids) > MAX_ENRICHMENT_GENE_IDS:
        msg = (
            f"gene_ids holds {len(ids)} identifiers; one enrichment call takes "
            f"at most {MAX_ENRICHMENT_GENE_IDS}."
        )
        raise ValidationError(detail=msg)
    return ids


async def enrich_gene_ids(
    site_id: str,
    gene_ids: list[str],
    background: BackgroundSource,
    enrichment_types: list[EnrichmentAnalysisType] | None = None,
) -> GeneIdEnrichment:
    """Run over-representation analysis on a gene list, with no stored set.

    The genes become a temporary WDK dataset addressed by a locus-tag search,
    and that step is the one every analysis type runs on.
    """
    ids = _clean_gene_ids(gene_ids)
    types = list(enrichment_types or ALL_ENRICHMENT_ANALYSIS_TYPES)

    search_name, parameters, record_type = await build_enrichment_params_from_gene_ids(
        site_id, ids
    )
    results, errors = await EnrichmentService(background).run_batch(
        site_id=site_id,
        analysis_types=types,
        search_name=search_name,
        record_type=record_type,
        parameters=parameters,
    )
    if len(errors) == len(types):
        msg = "Enrichment analysis failed: " + "; ".join(errors)
        raise InternalError(detail=msg)

    logger.info(
        "Enrichment ran on a gene list",
        site_id=site_id,
        gene_count=len(ids),
        analyses=[r.analysis_type for r in results],
    )
    return GeneIdEnrichment(
        site_id=site_id,
        gene_count=len(ids),
        background=background,
        analyses=[
            EnrichedAnalysis(
                analysis_type=r.analysis_type,
                source_columns=SOURCE_COLUMNS[r.analysis_type],
                terms=r.terms,
                error=r.error,
            )
            for r in results
        ],
    )
