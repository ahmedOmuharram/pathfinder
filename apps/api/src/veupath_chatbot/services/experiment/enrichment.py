"""Enrichment analysis via WDK step analysis API.

Wraps VEuPathDB's native GO, pathway, and word enrichment analyses
that are available through the step analysis endpoint.
"""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
    EnrichmentTerm,
)

logger = get_logger(__name__)

_ANALYSIS_TYPE_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "gene-go-enrichment",
    "go_component": "gene-go-enrichment",
    "go_process": "gene-go-enrichment",
    "pathway": "gene-pathway-enrichment",
    "word": "gene-word-enrichment",
}

_GO_ONTOLOGY_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "Molecular Function",
    "go_component": "Cellular Component",
    "go_process": "Biological Process",
}


def _parse_enrichment_terms(
    rows: list[JSONObject],
) -> list[EnrichmentTerm]:
    """Parse WDK enrichment result rows into structured terms."""
    terms: list[EnrichmentTerm] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        term_id = str(row.get("ID", row.get("id", "")))
        term_name = str(row.get("Description", row.get("description", "")))
        gene_count = _safe_int(row.get("ResultCount", row.get("resultCount", 0)))
        bg_count = _safe_int(row.get("BgdCount", row.get("bgdCount", 0)))
        fold = _safe_float(row.get("FoldEnrich", row.get("foldEnrichment", 0)))
        odds = _safe_float(row.get("OddsRatio", row.get("oddsRatio", 0)))
        pval = _safe_float(row.get("PValue", row.get("pValue", 1.0)))
        fdr = _safe_float(row.get("BenjaminiHochberg", row.get("benjamini", 1.0)))
        bonf = _safe_float(row.get("Bonferroni", row.get("bonferroni", 1.0)))

        genes_raw = row.get("ResultIDList", row.get("genes", []))
        genes: list[str] = []
        if isinstance(genes_raw, str):
            genes = [g.strip() for g in genes_raw.split(",") if g.strip()]
        elif isinstance(genes_raw, list):
            genes = [str(g) for g in genes_raw]

        terms.append(
            EnrichmentTerm(
                term_id=term_id,
                term_name=term_name,
                gene_count=gene_count,
                background_count=bg_count,
                fold_enrichment=fold,
                odds_ratio=odds,
                p_value=pval,
                fdr=fdr,
                bonferroni=bonf,
                genes=genes,
            )
        )
    return terms


async def run_enrichment_analysis(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
    analysis_type: EnrichmentAnalysisType,
) -> EnrichmentResult:
    """Run a single enrichment analysis on a search result set.

    Creates a temporary WDK strategy, runs the analysis, parses results,
    and cleans up.

    :param site_id: VEuPathDB site ID.
    :param record_type: WDK record type (e.g. "gene").
    :param search_name: WDK search/question name.
    :param parameters: Search parameters.
    :param analysis_type: Which enrichment to run.
    :returns: Parsed enrichment results.
    """
    api = get_strategy_api(site_id)

    step = await api.create_step(
        record_type=record_type,
        search_name=search_name,
        parameters=parameters or {},
        custom_name="Enrichment target",
    )
    step_id = _extract_step_id(step)

    root = StepTreeNode(step_id)
    strategy_id: int | None = None

    try:
        created = await api.create_strategy(
            step_tree=root,
            name="Pathfinder enrichment analysis",
            description=None,
            is_internal=True,
        )
        if isinstance(created, dict):
            raw_sid = created.get("id")
            if isinstance(raw_sid, int):
                strategy_id = raw_sid

        wdk_analysis_type = _ANALYSIS_TYPE_MAP.get(analysis_type)
        if not wdk_analysis_type:
            return EnrichmentResult(
                analysis_type=analysis_type,
                terms=[],
                total_genes_analyzed=0,
                background_size=0,
            )

        analysis_params: JSONObject = {}
        if analysis_type in _GO_ONTOLOGY_MAP:
            analysis_params["ontology"] = _GO_ONTOLOGY_MAP[analysis_type]

        result = await api.run_step_analysis(
            step_id=step_id,
            analysis_type=wdk_analysis_type,
            parameters=analysis_params,
        )

        rows = _extract_analysis_rows(result)
        terms = _parse_enrichment_terms(rows)

        total_analyzed = 0
        bg_size = 0
        if isinstance(result, dict):
            total_analyzed = _safe_int(
                result.get("resultSize", result.get("totalResults", 0))
            )
            bg_size = _safe_int(result.get("backgroundSize", result.get("bgdSize", 0)))

        return EnrichmentResult(
            analysis_type=analysis_type,
            terms=terms,
            total_genes_analyzed=total_analyzed,
            background_size=bg_size,
        )

    finally:
        if strategy_id is not None:
            try:
                await api.delete_strategy(strategy_id)
            except Exception as exc:
                logger.warning(
                    "Failed to cleanup enrichment strategy",
                    strategy_id=strategy_id,
                    error=str(exc),
                )


def _extract_step_id(payload: JSONObject | None) -> int:
    if isinstance(payload, dict):
        raw = payload.get("id")
        if isinstance(raw, int):
            return raw
    raise ValueError("Failed to extract step ID from WDK response")


def _extract_analysis_rows(result: JSONValue) -> list[JSONObject]:
    """Extract tabular rows from a WDK analysis result."""
    if not isinstance(result, dict):
        return []

    rows = result.get("rows", result.get("data", result.get("results", [])))
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def _safe_int(val: object, default: int = 0) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, (float, str)):
        try:
            return int(float(val))
        except ValueError, TypeError:
            pass
    return default


def _safe_float(val: object, default: float = 0.0) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            pass
    return default
