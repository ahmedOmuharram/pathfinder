"""Converts raw WDK enrichment results into structured terms and results."""

import json

from assistant_core.platform.types import JSONObject
from pydantic import JsonValue, ValidationError

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKEnrichmentResponse,
    WDKEnrichmentRowBase,
    WDKGoEnrichmentRow,
    WDKPathwayEnrichmentRow,
    WDKWordEnrichmentRow,
)
from pathfinder.services.enrichment.html import parse_result_genes_html
from pathfinder.services.enrichment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
    EnrichmentTerm,
)

ANALYSIS_TYPE_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "go-enrichment",
    "go_component": "go-enrichment",
    "go_process": "go-enrichment",
    "pathway": "pathway-enrichment",
    "word": "word-enrichment",
}

GO_ONTOLOGY_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "Molecular Function",
    "go_component": "Cellular Component",
    "go_process": "Biological Process",
}

_REVERSE_GO_ONTOLOGY: dict[str, EnrichmentAnalysisType] = {
    v: k for k, v in GO_ONTOLOGY_MAP.items()
}

_WDK_TO_ANALYSIS_TYPE: dict[str, EnrichmentAnalysisType] = {
    "pathway-enrichment": "pathway",
    "word-enrichment": "word",
}

ENRICHMENT_ANALYSIS_NAMES = frozenset(ANALYSIS_TYPE_MAP.values())

_GO_ANALYSIS_TYPES: frozenset[EnrichmentAnalysisType] = frozenset(
    {"go_function", "go_component", "go_process"}
)


def infer_enrichment_type(
    wdk_analysis_name: str,
    params: JSONObject,
    result: JsonValue,
) -> EnrichmentAnalysisType:
    """Infer the analysis type from a WDK analysis name.

    GO enrichment needs the ontology branch, which comes from the parameters or
    the result.
    """
    if wdk_analysis_name in _WDK_TO_ANALYSIS_TYPE:
        return _WDK_TO_ANALYSIS_TYPE[wdk_analysis_name]

    ontology = str(params.get("goAssociationsOntologies", ""))

    # A WDK vocabulary parameter arrives as a JSON array string.
    if ontology.startswith("["):
        try:
            parsed = json.loads(ontology)
            if isinstance(parsed, list) and parsed:
                ontology = str(parsed[0])
        except json.JSONDecodeError, ValueError:
            ontology = ""

    if not ontology and isinstance(result, dict):
        ontologies = result.get("goOntologies")
        if isinstance(ontologies, list) and ontologies:
            ontology = str(ontologies[0])
    return _REVERSE_GO_ONTOLOGY.get(ontology, "go_process")


def is_enrichment_analysis(wdk_analysis_name: str) -> bool:
    """Report whether a WDK analysis name belongs to an enrichment plugin."""
    return wdk_analysis_name in ENRICHMENT_ANALYSIS_NAMES


def upsert_enrichment_result(
    results: list[EnrichmentResult],
    new: EnrichmentResult,
) -> None:
    """Replace the result with the same analysis type in place, or append it."""
    for i, existing in enumerate(results):
        if existing.analysis_type == new.analysis_type:
            results[i] = new
            return
    results.append(new)


def parse_enrichment_response(result: JsonValue) -> WDKEnrichmentResponse:
    """Validate a raw WDK analysis result into a typed envelope."""
    if not isinstance(result, dict):
        return WDKEnrichmentResponse()
    try:
        return WDKEnrichmentResponse.model_validate(result)
    except ValidationError:
        return WDKEnrichmentResponse()


def _extract_genes(result_genes: str) -> tuple[int, list[str]]:
    """Extract the gene count and gene IDs from a WDK result-genes field.

    The field holds either an HTML link that carries both, or a plain count.
    """
    if "<" in result_genes:
        return parse_result_genes_html(result_genes)
    try:
        return int(float(result_genes)), []
    except ValueError, TypeError:
        return 0, []


def _row_to_term(
    row: WDKEnrichmentRowBase,
    term_id: str,
    term_name: str,
) -> EnrichmentTerm:
    """Map a WDK enrichment row to a domain term.

    The raw string values pass through unchanged. The term model coerces them.
    """
    gene_count, genes = _extract_genes(row.result_genes)
    return EnrichmentTerm.model_validate(
        {
            "term_id": term_id,
            "term_name": term_name,
            "gene_count": gene_count,
            "background_count": row.bgd_genes,
            "fold_enrichment": row.fold_enrich,
            "odds_ratio": row.odds_ratio,
            "p_value": row.p_value,
            "fdr": row.benjamini,
            "bonferroni": row.bonferroni,
            "genes": genes,
        }
    )


def parse_enrichment_terms(
    rows: list[JSONObject],
    analysis_type: EnrichmentAnalysisType = "go_process",
) -> list[EnrichmentTerm]:
    """Parse WDK enrichment result rows into structured terms."""
    terms: list[EnrichmentTerm] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            wdk_row: WDKEnrichmentRowBase
            term_id: str
            term_name: str
            if analysis_type in _GO_ANALYSIS_TYPES:
                go_row = WDKGoEnrichmentRow.model_validate(row)
                wdk_row, term_id, term_name = go_row, go_row.go_id, go_row.go_term
            elif analysis_type == "pathway":
                pw_row = WDKPathwayEnrichmentRow.model_validate(row)
                wdk_row, term_id, term_name = (
                    pw_row,
                    pw_row.pathway_id,
                    pw_row.pathway_name,
                )
            else:
                wd_row = WDKWordEnrichmentRow.model_validate(row)
                wdk_row, term_id, term_name = wd_row, wd_row.word, wd_row.pathway_name
            terms.append(_row_to_term(wdk_row, term_id, term_name))
        except ValidationError:
            continue
    return terms


def derive_total_analyzed(rows: list[JSONObject]) -> int:
    """Derive the input-set size from the per-row result percentage.

    WDK gives no result-level total. The row with the most result genes has the
    least rounding error.
    """
    total = 0
    best_result_genes = 0
    for row in rows:
        try:
            base = WDKEnrichmentRowBase.model_validate(row)
            percent = float(base.percent_in_result or "0")
        except ValueError, ValidationError:
            continue
        result_genes, _ = _extract_genes(base.result_genes)
        if percent > 0 and result_genes > best_result_genes:
            best_result_genes = result_genes
            total = round(result_genes * 100 / percent)
    return total


def parse_enrichment_from_raw(
    wdk_analysis_name: str,
    params: JSONObject,
    result: JsonValue,
) -> EnrichmentResult:
    """Parse a raw WDK analysis result into an enrichment result."""
    analysis_type = infer_enrichment_type(wdk_analysis_name, params, result)
    envelope = parse_enrichment_response(result)
    terms = parse_enrichment_terms(envelope.result_data, analysis_type)
    return EnrichmentResult(
        analysis_type=analysis_type,
        terms=terms,
        total_genes_analyzed=derive_total_analyzed(envelope.result_data),
    )
