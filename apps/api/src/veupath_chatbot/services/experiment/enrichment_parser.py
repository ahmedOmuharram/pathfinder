"""WDK enrichment result parsing and type inference.

Pure module (no I/O). Converts raw WDK enrichment analysis results
into structured ``EnrichmentTerm`` and ``EnrichmentResult`` objects.
Handles the various field name conventions used by different WDK
enrichment plugins (GO, pathway, word).
"""

import json

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.enrichment_html import parse_result_genes_html
from veupath_chatbot.services.experiment.helpers import safe_float, safe_int
from veupath_chatbot.services.experiment.types import (
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


def extract_result_totals(result: JSONValue) -> tuple[int, int]:
    """Extract total-analyzed and background-size from a WDK result dict.

    WDK enrichment plugins use different keys for the same concepts:
    ``resultSize`` / ``totalResults`` for the gene count, and
    ``backgroundSize`` / ``bgdSize`` for the background universe.

    :returns: ``(total_genes_analyzed, background_size)``
    """
    if not isinstance(result, dict):
        return 0, 0
    total = safe_int(result.get("resultSize", result.get("totalResults", 0)))
    bg = safe_int(result.get("backgroundSize", result.get("bgdSize", 0)))
    return total, bg


def parse_enrichment_terms(
    rows: list[JSONObject],
) -> list[EnrichmentTerm]:
    """Parse WDK enrichment result rows into structured terms.

    Handles both the "standard" field names used by some WDK analysis
    plugins and the field names returned by the GO/pathway/word enrichment
    plugins (``goId``, ``goTerm``, ``resultGenes`` as HTML, ``bgdGenes``,
    ``foldEnrich``, etc.).
    """
    terms: list[EnrichmentTerm] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        # Term identifier — plugins use different keys:
        #   GO: goId, Pathway: pathwayId, Word: word (no separate ID)
        term_id = str(
            row.get(
                "ID",
                row.get(
                    "id",
                    row.get(
                        "goId",
                        row.get("pathwayId", row.get("word", "")),
                    ),
                ),
            )
        )
        # Term name / description — Word enrichment uses "descrip" (truncated).
        term_name = str(
            row.get(
                "Description",
                row.get(
                    "description",
                    row.get(
                        "goTerm",
                        row.get(
                            "pathwayName",
                            row.get("descrip", row.get("word", "")),
                        ),
                    ),
                ),
            )
        )

        # Gene count + gene list — WDK enrichment returns resultGenes as
        # an HTML <a> tag embedding the count and gene IDs in the URL.
        gene_count: int = 0
        genes: list[str] = []

        result_count_raw = row.get("ResultCount", row.get("resultCount"))
        if result_count_raw is not None:
            gene_count = safe_int(result_count_raw)
        else:
            result_genes_raw = row.get("resultGenes", "")
            if isinstance(result_genes_raw, str) and "<" in result_genes_raw:
                gene_count, genes = parse_result_genes_html(result_genes_raw)
            else:
                gene_count = safe_int(result_genes_raw)

        # If genes weren't extracted from HTML, try explicit gene list fields
        if not genes:
            genes_raw = row.get("ResultIDList", row.get("genes"))
            if isinstance(genes_raw, str):
                genes = [g.strip() for g in genes_raw.split(",") if g.strip()]
            elif isinstance(genes_raw, list):
                genes = [str(g) for g in genes_raw]

        bg_count = safe_int(
            row.get("BgdCount", row.get("bgdCount", row.get("bgdGenes", 0)))
        )
        fold = safe_float(
            row.get("FoldEnrich", row.get("foldEnrichment", row.get("foldEnrich", 0)))
        )
        odds = safe_float(row.get("OddsRatio", row.get("oddsRatio", 0)))
        pval = safe_float(row.get("PValue", row.get("pValue", 1.0)), default=1.0)
        fdr = safe_float(
            row.get("BenjaminiHochberg", row.get("benjamini", 1.0)), default=1.0
        )
        bonf = safe_float(
            row.get("Bonferroni", row.get("bonferroni", 1.0)), default=1.0
        )

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


def extract_analysis_rows(result: JSONValue) -> list[JSONObject]:
    """Extract tabular rows from a WDK analysis result.

    WDK enrichment plugins (GO, pathway, word) return rows under
    ``resultData``; other plugins may use ``rows``, ``data``, or ``results``.
    """
    if not isinstance(result, dict):
        return []

    rows = result.get(
        "resultData",
        result.get("rows", result.get("data", result.get("results", []))),
    )
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def parse_enrichment_from_raw(
    wdk_analysis_name: str,
    params: JSONObject,
    result: JSONValue,
) -> EnrichmentResult:
    """Parse a raw WDK analysis result into an ``EnrichmentResult``.

    Used by the generic ``analyses/run`` endpoint to return structured
    enrichment data instead of raw JSON.
    """
    analysis_type = infer_enrichment_type(wdk_analysis_name, params, result)
    rows = extract_analysis_rows(result)
    terms = parse_enrichment_terms(rows)
    total_analyzed, bg_size = extract_result_totals(result)

    return EnrichmentResult(
        analysis_type=analysis_type,
        terms=terms,
        total_genes_analyzed=total_analyzed,
        background_size=bg_size,
    )
