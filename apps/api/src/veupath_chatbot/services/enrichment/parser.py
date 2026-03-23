"""WDK enrichment result parsing and type inference.

Pure module (no I/O). Converts raw WDK enrichment analysis results
into structured ``EnrichmentTerm`` and ``EnrichmentResult`` objects.
Uses typed WDK models for validation instead of manual ``.get()`` chains.
"""

import json

from pydantic import ValidationError

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKEnrichmentResponse,
    WDKEnrichmentRowBase,
    WDKGoEnrichmentRow,
    WDKPathwayEnrichmentRow,
    WDKWordEnrichmentRow,
)
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.enrichment.html import parse_result_genes_html
from veupath_chatbot.services.enrichment.types import (
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
    result: JSONValue,
) -> EnrichmentAnalysisType:
    """Infer the ``EnrichmentAnalysisType`` from a WDK analysis name.

    For GO enrichment, uses the ``goAssociationsOntologies`` parameter or
    the ``goOntologies`` field in the result to determine which GO branch.
    """
    if wdk_analysis_name in _WDK_TO_ANALYSIS_TYPE:
        return _WDK_TO_ANALYSIS_TYPE[wdk_analysis_name]

    # GO enrichment — determine which ontology
    ontology = str(params.get("goAssociationsOntologies", ""))

    # WDK vocab params arrive as JSON array strings, e.g. '["Molecular Function"]'.
    # Unwrap the first element so it matches _REVERSE_GO_ONTOLOGY keys.
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
    """Return True if the WDK analysis name is an enrichment plugin."""
    return wdk_analysis_name in ENRICHMENT_ANALYSIS_NAMES


def upsert_enrichment_result(
    results: list[EnrichmentResult],
    new: EnrichmentResult,
) -> None:
    """Replace an existing result of the same ``analysis_type``, or append.

    Mutates *results* in-place so callers don't accumulate duplicate
    tabs when the same enrichment analysis is re-run.
    """
    for i, existing in enumerate(results):
        if existing.analysis_type == new.analysis_type:
            results[i] = new
            return
    results.append(new)


def parse_enrichment_response(result: JSONValue) -> WDKEnrichmentResponse:
    """Validate a raw WDK analysis result into a typed envelope."""
    if not isinstance(result, dict):
        return WDKEnrichmentResponse()
    try:
        return WDKEnrichmentResponse.model_validate(result)
    except ValidationError:
        return WDKEnrichmentResponse()


def _extract_genes(result_genes: str) -> tuple[int, list[str]]:
    """Extract gene count and IDs from a WDK resultGenes field.

    WDK returns resultGenes as either:
    - HTML: ``<a href='?idList=G1,G2,...'>2</a>`` -- parse count + IDs
    - Plain count string: ``"46"`` -- parse as int, no IDs
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
    """Map a WDK enrichment row to a domain EnrichmentTerm.

    Passes raw WDK string values directly — Pydantic lax mode on
    ``EnrichmentTerm`` coerces str→int/float, and ``SafeFiniteFloat``
    clamps ``"Infinity"`` → 0.0.
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


def parse_enrichment_from_raw(
    wdk_analysis_name: str,
    params: JSONObject,
    result: JSONValue,
) -> EnrichmentResult:
    """Parse a raw WDK analysis result into an ``EnrichmentResult``."""
    analysis_type = infer_enrichment_type(wdk_analysis_name, params, result)
    envelope = parse_enrichment_response(result)
    terms = parse_enrichment_terms(envelope.result_data, analysis_type)
    return EnrichmentResult(
        analysis_type=analysis_type,
        terms=terms,
    )
