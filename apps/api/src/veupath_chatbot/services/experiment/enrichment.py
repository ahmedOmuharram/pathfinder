"""Enrichment analysis via WDK step analysis API.

Orchestrates VEuPathDB's native GO, pathway, and word enrichment analyses.
Delegates parsing to ``enrichment_parser``, HTML extraction to
``enrichment_html``, and parameter encoding to ``enrichment_params``.
"""

import asyncio
import json

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.experiment.enrichment_params import (
    extract_default_params,
    extract_vocab_values,
)
from veupath_chatbot.services.experiment.enrichment_parser import (
    ANALYSIS_TYPE_MAP,
    GO_ONTOLOGY_MAP,
    extract_analysis_rows,
    extract_result_totals,
    parse_enrichment_terms,
)
from veupath_chatbot.services.experiment.helpers import (
    coerce_step_id,
    extract_wdk_id,
)
from veupath_chatbot.services.experiment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)

logger = get_logger(__name__)


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
    wdk_analysis_type = ANALYSIS_TYPE_MAP.get(analysis_type)
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
        analysis_params = extract_default_params(form_meta)
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
    # requested ontology is actually available on this site.
    if analysis_type in GO_ONTOLOGY_MAP:
        requested_ontology = GO_ONTOLOGY_MAP[analysis_type]
        available = extract_vocab_values(form_meta, "goAssociationsOntologies")

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
                await asyncio.sleep(2**attempt)
                continue
            raise
    else:
        if last_err is not None:
            raise last_err
        msg = "Enrichment analysis failed after retries"
        raise RuntimeError(msg)

    rows = extract_analysis_rows(result)
    terms = parse_enrichment_terms(rows)
    total_analyzed, bg_size = extract_result_totals(result)

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
    """Run a single enrichment analysis on a search result set."""
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
    """Run enrichment on an already-persisted WDK step."""
    api = get_strategy_api(site_id)
    return await _execute_analysis(api, step_id, analysis_type)
