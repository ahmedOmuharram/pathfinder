"""Unified enrichment service.

Single entry point for running enrichment analyses regardless of
whether the caller is an experiment endpoint, gene set endpoint,
or AI tool.

Rate limiting
-------------
A process-level semaphore (``_WDK_ENRICHMENT_SEMAPHORE``) limits how
many ``run_batch`` calls can execute concurrently across the entire
application.  Within a single batch, analyses run in parallel via
``asyncio.gather`` to keep total wall-clock time within proxy timeouts.
"""

import asyncio
import json

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.platform.errors import AppError, InternalError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.enrichment.params import (
    extract_default_params,
    extract_vocab_values,
)
from veupath_chatbot.services.enrichment.parser import (
    ANALYSIS_TYPE_MAP,
    GO_ONTOLOGY_MAP,
    parse_enrichment_response,
    parse_enrichment_terms,
)
from veupath_chatbot.services.enrichment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)

logger = get_logger(__name__)

# Limit concurrent enrichment batches process-wide.
# WDK's step analysis API becomes unreliable under parallel load.
# This limits how many run_batch calls execute simultaneously, not
# individual analyses within a batch.
_WDK_ENRICHMENT_SEMAPHORE = asyncio.Semaphore(3)


class EnrichmentService:
    """Unified enrichment dispatcher."""

    async def run(
        self,
        *,
        site_id: str,
        analysis_type: EnrichmentAnalysisType,
        step_id: int | None = None,
        search_name: str | None = None,
        record_type: str | None = None,
        parameters: JSONObject | None = None,
    ) -> EnrichmentResult:
        """Run a single enrichment analysis.

        If step_id is provided, runs on the existing step.
        Otherwise creates a temporary strategy from search_name/parameters.
        """
        api = get_strategy_api(site_id)

        if step_id is not None:
            return await self._execute_analysis(api, step_id, analysis_type)

        if not search_name or parameters is None:
            msg = "Either step_id or search_name+parameters required"
            raise ValidationError(detail=msg)

        step = await api.create_step(
            NewStepSpec(
                search_name=search_name,
                search_config=WDKSearchConfig(
                    parameters={
                        k: str(v)
                        for k, v in (parameters or {}).items()
                        if v is not None
                    },
                ),
                custom_name="Enrichment target",
            ),
            record_type=record_type or "transcript",
        )
        root = WDKStepTree(step_id=step.id)
        strategy_id: int | None = None

        try:
            created = await api.create_strategy(
                step_tree=root,
                name="Pathfinder enrichment analysis",
                description=None,
                is_internal=True,
            )
            strategy_id = created.id
            return await self._execute_analysis(api, step.id, analysis_type)
        finally:
            await delete_temp_strategy(api, strategy_id)

    async def run_batch(
        self,
        *,
        site_id: str,
        analysis_types: list[EnrichmentAnalysisType],
        step_id: int | None = None,
        search_name: str | None = None,
        record_type: str | None = None,
        parameters: JSONObject | None = None,
    ) -> tuple[list[EnrichmentResult], list[str]]:
        """Run multiple enrichment analyses concurrently on a shared step.

        When no step_id is provided (paste gene sets), creates ONE temporary
        WDK step/strategy and runs all analysis types against it — instead
        of creating N separate temp strategies.  This reduces WDK API calls
        from ~5N to ~N+3 and avoids rate-limit 500s.
        """
        errors: list[str] = []

        # If we already have a step, run all analyses on it directly.
        if step_id is not None:
            async with _WDK_ENRICHMENT_SEMAPHORE:
                return await self._run_analyses_on_step(
                    site_id,
                    step_id,
                    analysis_types,
                    errors,
                )

        # No step — need search_name + parameters to create one.
        if not search_name or parameters is None:
            msg = "Either step_id or search_name+parameters required"
            raise ValidationError(detail=msg)

        # Create ONE temp step/strategy, run all analyses, then clean up.
        api = get_strategy_api(site_id)
        step = await api.create_step(
            NewStepSpec(
                search_name=search_name,
                search_config=WDKSearchConfig(
                    parameters={
                        k: str(v)
                        for k, v in (parameters or {}).items()
                        if v is not None
                    },
                ),
                custom_name="Enrichment target",
            ),
            record_type=record_type or "transcript",
        )
        shared_step_id = step.id
        root = WDKStepTree(step_id=shared_step_id)
        strategy_id: int | None = None

        async with _WDK_ENRICHMENT_SEMAPHORE:
            try:
                created = await api.create_strategy(
                    step_tree=root,
                    name="Pathfinder enrichment analysis",
                    description=None,
                    is_internal=True,
                )
                strategy_id = created.id

                return await self._run_analyses_on_step(
                    site_id,
                    shared_step_id,
                    analysis_types,
                    errors,
                )
            finally:
                await delete_temp_strategy(api, strategy_id)

    async def _execute_analysis(
        self,
        api: StrategyAPI,
        step_id: int,
        analysis_type: EnrichmentAnalysisType,
    ) -> EnrichmentResult:
        """Run one analysis on a step, parse results, return EnrichmentResult.

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
        form_meta_raw: JSONValue = None
        try:
            form_meta = await api.get_analysis_type(step_id, wdk_analysis_type)
            form_meta_raw = form_meta.model_dump(by_alias=True)
            analysis_params = extract_default_params(form_meta_raw)
            logger.debug(
                "Fetched analysis form defaults",
                analysis_type=wdk_analysis_type,
                param_names=list(analysis_params.keys()),
            )
        except AppError as exc:
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
            available = extract_vocab_values(form_meta_raw, "goAssociationsOntologies")

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

            analysis_params["goAssociationsOntologies"] = json.dumps(
                [requested_ontology]
            )

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
            except AppError as exc:
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
            raise InternalError(detail=msg)

        envelope = parse_enrichment_response(result)
        terms = parse_enrichment_terms(envelope.result_data, analysis_type)

        return EnrichmentResult(
            analysis_type=analysis_type,
            terms=terms,
        )

    async def _run_analyses_on_step(
        self,
        site_id: str,
        step_id: int,
        analysis_types: list[EnrichmentAnalysisType],
        errors: list[str],
    ) -> tuple[list[EnrichmentResult], list[str]]:
        """Run multiple analysis types on a single step concurrently.

        Analyses run in parallel to keep total wall-clock time under
        proxy timeouts (~30s instead of ~90s sequential).  A process-level
        semaphore still limits how many ``run_batch`` calls execute
        concurrently across different requests.
        """
        api = get_strategy_api(site_id)

        async def _run_one(
            analysis_type: EnrichmentAnalysisType,
        ) -> EnrichmentResult:
            try:
                return await self._execute_analysis(api, step_id, analysis_type)
            except (AppError, RuntimeError) as exc:
                logger.warning(
                    "Enrichment failed",
                    analysis_type=analysis_type,
                    error=str(exc),
                )
                error_msg = str(exc)
                errors.append(f"{analysis_type}: {error_msg}")
                return EnrichmentResult(
                    analysis_type=analysis_type,
                    terms=[],
                    total_genes_analyzed=0,
                    background_size=0,
                    error=error_msg,
                )

        results = list(
            await asyncio.gather(*[_run_one(t) for t in analysis_types])
        )
        return results, errors
