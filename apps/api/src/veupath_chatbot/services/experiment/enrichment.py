"""Enrichment analysis via WDK step analysis API.

Wraps VEuPathDB's native GO, pathway, and word enrichment analyses
that are available through the step analysis endpoint.

Plugin names (from ``stepAnalysisPlugins.xml``):
  - ``go-enrichment``  → GoEnrichmentPlugin
  - ``pathway-enrichment``  → PathwaysEnrichmentPlugin
  - ``word-enrichment``  → WordEnrichmentPlugin

GO enrichment parameters (from ``GoEnrichmentPlugin.java``):
  - ``goAssociationsOntologies``  — "Molecular Function" / etc.
  - ``goEvidenceCodes``  — evidence code filter
  - ``goSubset``  — GO slim subset
  - ``pValueCutoff``  — p-value threshold
  - ``organism``  — organism filter

Parameters are fetched from the WDK analysis form defaults so required
fields like ``organism`` and ``pValueCutoff`` are always populated.
"""

import json
import re

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.experiment.helpers import (
    coerce_step_id,
    extract_wdk_id,
    safe_float,
    safe_int,
)
from veupath_chatbot.services.experiment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
    EnrichmentTerm,
)

logger = get_logger(__name__)

_ANALYSIS_TYPE_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "go-enrichment",
    "go_component": "go-enrichment",
    "go_process": "go-enrichment",
    "pathway": "pathway-enrichment",
    "word": "word-enrichment",
}

_GO_ONTOLOGY_MAP: dict[EnrichmentAnalysisType, str] = {
    "go_function": "Molecular Function",
    "go_component": "Cellular Component",
    "go_process": "Biological Process",
}

_REVERSE_GO_ONTOLOGY: dict[str, EnrichmentAnalysisType] = {
    v: k for k, v in _GO_ONTOLOGY_MAP.items()
}

_WDK_TO_ANALYSIS_TYPE: dict[str, EnrichmentAnalysisType] = {
    "pathway-enrichment": "pathway",
    "word-enrichment": "word",
}

_ENRICHMENT_ANALYSIS_NAMES = frozenset(_ANALYSIS_TYPE_MAP.values())


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
    return wdk_analysis_name in _ENRICHMENT_ANALYSIS_NAMES


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


def _extract_result_totals(result: JSONValue) -> tuple[int, int]:
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
    rows = _extract_analysis_rows(result)
    terms = _parse_enrichment_terms(rows)
    total_analyzed, bg_size = _extract_result_totals(result)

    return EnrichmentResult(
        analysis_type=analysis_type,
        terms=terms,
        total_genes_analyzed=total_analyzed,
        background_size=bg_size,
    )


_LINK_COUNT_RE = re.compile(r">(\d+)<")
_IDLIST_RE = re.compile(r"idList=([^&'\"]+)")


def _parse_result_genes_html(html: str) -> tuple[int, list[str]]:
    """Extract gene count and gene IDs from a WDK ``resultGenes`` HTML link.

    WDK enrichment plugins render gene counts as hyperlinks::

        <a href='...?param.ds_gene_ids.idList=GENE1,GENE2,...&autoRun=1'>32</a>

    Returns ``(count, gene_ids)``.
    """
    count = 0
    count_m = _LINK_COUNT_RE.search(html)
    if count_m:
        count = int(count_m.group(1))

    genes: list[str] = []
    id_m = _IDLIST_RE.search(html)
    if id_m:
        genes = [g.strip() for g in id_m.group(1).split(",") if g.strip()]
    return count, genes


def _parse_enrichment_terms(
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
                gene_count, genes = _parse_result_genes_html(result_genes_raw)
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


# WDK ``EnumParamFormatter.getParamType()`` emits these JSON type strings
# for params extending ``AbstractEnumParam`` (``EnumParam``, ``FlatVocabParam``).
# These are the only param types whose stable values must be JSON arrays
# (via ``AbstractEnumParam.convertToTerms()`` → ``new JSONArray(stableValue)``).
# See ``org.gusdb.wdk.core.api.JsonKeys``:
#   SINGLE_VOCAB_PARAM_TYPE = "single-pick-vocabulary"
#   MULTI_VOCAB_PARAM_TYPE  = "multi-pick-vocabulary"
_WDK_VOCAB_PARAM_TYPES = frozenset({"single-pick-vocabulary", "multi-pick-vocabulary"})


def _extract_param_specs(form_meta: JSONValue) -> list[JSONObject]:
    """Extract the parameters list from WDK form metadata.

    Handles the ``searchData`` wrapper that WDK uses for analysis-type
    endpoints and unwraps it if present.
    """
    if not isinstance(form_meta, dict):
        return []
    container = unwrap_search_data(form_meta) or form_meta
    params_raw = container.get("parameters")
    if not isinstance(params_raw, list):
        return []
    return [p for p in params_raw if isinstance(p, dict)]


def _extract_vocab_values(form_meta: JSONValue, param_name: str) -> list[str]:
    """Extract the allowed vocabulary values for a parameter from form metadata.

    WDK vocabulary params include a ``vocabulary`` field — a list of
    ``[value, display, null]`` triples.  Returns the list of ``value``
    strings (first element of each triple).

    Returns an empty list if the parameter is not found or has no vocabulary.
    """
    for p in _extract_param_specs(form_meta):
        if p.get("name") != param_name:
            continue
        vocab = p.get("vocabulary")
        if not isinstance(vocab, list):
            return []
        return [str(entry[0]) for entry in vocab if isinstance(entry, list) and entry]
    return []


def _build_param_type_map(form_meta: JSONValue) -> dict[str, str]:
    """Build a ``{param_name: wdk_type}`` map from form metadata.

    Used by :func:`encode_vocab_params` to know which params need
    JSON array encoding after a merge with user-supplied values.
    """
    type_map: dict[str, str] = {}
    for p in _extract_param_specs(form_meta):
        name = p.get("name")
        ptype = p.get("type")
        if isinstance(name, str) and name and isinstance(ptype, str):
            type_map[name] = ptype
    return type_map


def _encode_vocab_value(value: str) -> str:
    """Ensure a vocabulary param value is a JSON array string.

    ``AbstractEnumParam.convertToTerms()`` calls
    ``new JSONArray(stableValue)`` — plain strings cause a parse error.
    Multi-pick values already arrive as JSON arrays from WDK; single-pick
    values arrive as plain strings and must be wrapped.
    """
    if value.startswith("["):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError, ValueError:
            pass
    return json.dumps([value])


def encode_vocab_params(
    params: JSONObject,
    form_meta: JSONValue,
) -> JSONObject:
    """Encode vocabulary param values as JSON arrays using form metadata.

    WDK's ``AbstractEnumParam.convertToTerms()`` requires all
    ``single-pick-vocabulary`` and ``multi-pick-vocabulary`` param values
    to be JSON-encoded arrays.  This function ensures that encoding is
    applied **after** merging defaults with user params, so user-supplied
    plain strings don't bypass the encoding.

    Params whose type is not in the form metadata, or whose type is not
    a vocabulary type, are returned unchanged.
    """
    type_map = _build_param_type_map(form_meta)
    if not type_map:
        return params

    encoded: JSONObject = {}
    for name, value in params.items():
        ptype = type_map.get(name, "") if isinstance(name, str) else ""
        if ptype in _WDK_VOCAB_PARAM_TYPES and isinstance(value, str):
            encoded[name] = _encode_vocab_value(value)
        else:
            encoded[name] = value
    return encoded


def _extract_default_params(form_meta: JSONValue) -> JSONObject:
    """Extract parameter names and default values from WDK analysis form metadata.

    WDK wraps data under ``searchData`` — the response from
    ``GET /analysis-types/{name}`` has the structure::

        { "searchData": { "parameters": [ {name, initialDisplayValue, ...}, ... ] } }

    Uses :func:`unwrap_search_data` to normalize the nesting, then
    extracts ``name``/``initialDisplayValue`` from each parameter spec.

    WDK's ``ParamFormatter.java`` emits ``initialDisplayValue`` (via
    ``JsonKeys.INITIAL_DISPLAY_VALUE``) as the stable default value.

    Vocabulary params (``single-pick-vocabulary``, ``multi-pick-vocabulary``)
    are encoded as JSON arrays per ``AbstractEnumParam.convertToTerms()``.
    """
    defaults: JSONObject = {}
    for p in _extract_param_specs(form_meta):
        name = p.get("name")
        default = p.get("initialDisplayValue")
        if not isinstance(name, str) or not name or default is None:
            continue

        value = str(default)

        # Vocab params must be JSON arrays for convertToTerms().
        param_type = str(p.get("type", ""))
        if param_type in _WDK_VOCAB_PARAM_TYPES:
            value = _encode_vocab_value(value)

        defaults[name] = value
    return defaults


async def _execute_analysis(
    api: StrategyAPI,
    step_id: int,
    analysis_type: EnrichmentAnalysisType,
) -> EnrichmentResult:
    """Shared logic: run analysis on a step, parse results, return EnrichmentResult.

    Fetches the analysis form metadata from WDK to discover correct
    parameter names and defaults, then overrides only the GO ontology
    parameter when applicable.
    """
    wdk_analysis_type = _ANALYSIS_TYPE_MAP.get(analysis_type)
    if not wdk_analysis_type:
        return EnrichmentResult(
            analysis_type=analysis_type,
            terms=[],
            total_genes_analyzed=0,
            background_size=0,
        )

    # Fetch form metadata so we use correct parameter names and defaults.
    analysis_params: JSONObject = {}
    form_meta: JSONValue = None
    try:
        form_meta = await api.get_analysis_type(step_id, wdk_analysis_type)
        analysis_params = _extract_default_params(form_meta)
        logger.debug(
            "Fetched analysis form defaults",
            analysis_type=wdk_analysis_type,
            param_names=list(analysis_params.keys()),
        )
    except Exception as exc:
        logger.warning(
            "Could not fetch analysis form metadata, using empty params",
            analysis_type=wdk_analysis_type,
            step_id=step_id,
            error=str(exc),
        )

    # For GO enrichment, set the ontology parameter — but only if the
    # requested ontology is actually available on this site.  Different
    # VEuPathDB sites support different GO ontologies (e.g. ToxoDB lacks
    # "Biological Process").
    if analysis_type in _GO_ONTOLOGY_MAP:
        requested_ontology = _GO_ONTOLOGY_MAP[analysis_type]
        available = _extract_vocab_values(form_meta, "goAssociationsOntologies")

        if available and requested_ontology not in available:
            logger.info(
                "GO ontology not available on this site, skipping",
                analysis_type=analysis_type,
                requested=requested_ontology,
                available=available,
            )
            return EnrichmentResult(
                analysis_type=analysis_type,
                terms=[],
                total_genes_analyzed=0,
                background_size=0,
            )

        analysis_params["goAssociationsOntologies"] = json.dumps([requested_ontology])

    logger.info(
        "Running enrichment analysis",
        analysis_type=analysis_type,
        wdk_type=wdk_analysis_type,
        step_id=step_id,
        params=analysis_params,
    )

    # Retry on WDK 500s — the step analysis endpoint is flaky under load.
    import asyncio as _asyncio

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            result = await api.run_step_analysis(
                step_id=step_id,
                analysis_type=wdk_analysis_type,
                parameters=analysis_params,
            )
            break
        except Exception as exc:
            last_err = exc
            err_str = str(exc)
            if "500" in err_str or "502" in err_str or "503" in err_str:
                logger.warning(
                    "WDK enrichment 5xx, retrying",
                    attempt=attempt + 1,
                    analysis_type=wdk_analysis_type,
                    error=err_str,
                )
                await _asyncio.sleep(2**attempt)
                continue
            raise
    else:
        if last_err is not None:
            raise last_err
        raise RuntimeError("Enrichment analysis failed after retries")

    rows = _extract_analysis_rows(result)
    terms = _parse_enrichment_terms(rows)
    total_analyzed, bg_size = _extract_result_totals(result)

    return EnrichmentResult(
        analysis_type=analysis_type,
        terms=terms,
        total_genes_analyzed=total_analyzed,
        background_size=bg_size,
    )


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
    """
    api = get_strategy_api(site_id)

    step = await api.create_step(
        record_type=record_type,
        search_name=search_name,
        parameters=parameters or {},
        custom_name="Enrichment target",
    )
    step_id = coerce_step_id(step)

    root = StepTreeNode(step_id)
    strategy_id: int | None = None

    try:
        created = await api.create_strategy(
            step_tree=root,
            name="Pathfinder enrichment analysis",
            description=None,
            is_internal=True,
        )
        strategy_id = extract_wdk_id(created)

        return await _execute_analysis(api, step_id, analysis_type)

    finally:
        await delete_temp_strategy(api, strategy_id)


async def run_enrichment_on_step(
    *,
    site_id: str,
    step_id: int,
    analysis_type: EnrichmentAnalysisType,
) -> EnrichmentResult:
    """Run enrichment on an already-persisted WDK step.

    Used for multi-step experiments where the strategy already exists.
    """
    api = get_strategy_api(site_id)
    return await _execute_analysis(api, step_id, analysis_type)


def _extract_analysis_rows(result: JSONValue) -> list[JSONObject]:
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
