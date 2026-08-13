"""Single entry point for running WDK enrichment analyses, for experiment
endpoints, gene set endpoints, and AI tools alike."""

import asyncio
import json

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.value_decoding import encode_params
from pathfinder.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.errors import AppError, InternalError, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.control_helpers import delete_temp_strategy
from pathfinder.services.enrichment.params import (
    extract_default_params,
    extract_vocab_values,
)
from pathfinder.services.enrichment.parser import (
    ANALYSIS_TYPE_MAP,
    GO_ONTOLOGY_MAP,
    derive_total_analyzed,
    parse_enrichment_response,
    parse_enrichment_terms,
)
from pathfinder.services.enrichment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)

logger = get_logger(__name__)

# WDK step analysis is unreliable under parallel load, so batches are capped
# process-wide. The cap applies to batches, not to analyses within a batch.
_WDK_ENRICHMENT_SEMAPHORE = asyncio.Semaphore(3)


class EnrichmentService:
    """Unified enrichment dispatcher."""

    async def run_batch(
        self,
        *,
        site_id: str,
        analysis_types: list[EnrichmentAnalysisType],
        step_id: int | None = None,
        search_name: str | None = None,
        record_type: str | None = None,
        parameters: dict[str, ParamValue] | None = None,
    ) -> tuple[list[EnrichmentResult], list[str]]:
        """Run multiple enrichment analyses concurrently on a shared step.

        Without a step id, one temporary step and strategy serves every
        analysis type, which keeps the WDK call count low.
        """
        errors: list[str] = []

        if step_id is not None:
            async with _WDK_ENRICHMENT_SEMAPHORE:
                return await self._run_analyses_on_step(
                    site_id,
                    step_id,
                    analysis_types,
                    errors,
                )

        if not search_name or parameters is None:
            msg = "Either step_id or search_name+parameters required"
            raise ValidationError(detail=msg)

        api = get_strategy_api(site_id)
        step = await api.create_step(
            NewStepSpec(
                search_name=search_name,
                search_config=WDKSearchConfig(parameters=encode_params(parameters)),
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
        """Run one analysis on a step and parse the result.

        Parameter names and defaults come from the WDK analysis form metadata.
        Only the GO ontology parameter is overridden.
        """
        wdk_analysis_type = ANALYSIS_TYPE_MAP.get(analysis_type)
        if not wdk_analysis_type:
            return EnrichmentResult(
                analysis_type=analysis_type,
                terms=[],
                total_genes_analyzed=0,
                background_size=0,
            )

        # Analysis creation validates with no fill, so the form's values are the
        # only source of the parameters it demands.
        form_meta = await api.get_analysis_type(step_id, wdk_analysis_type)
        wdk_params: list[WDKParameter] = form_meta.search_data.parameters or []
        analysis_params: JSONObject = extract_default_params(wdk_params)
        logger.debug(
            "Fetched analysis form defaults",
            analysis_type=wdk_analysis_type,
            param_names=list(analysis_params.keys()),
        )

        # The set of GO ontologies differs per site.
        if analysis_type in GO_ONTOLOGY_MAP:
            requested_ontology = GO_ONTOLOGY_MAP[analysis_type]
            available = extract_vocab_values(wdk_params, "goAssociationsOntologies")

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

        # The WDK step analysis endpoint returns 5xx under load, so retry it.
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
            total_genes_analyzed=derive_total_analyzed(envelope.result_data),
        )

    async def _run_analyses_on_step(
        self,
        site_id: str,
        step_id: int,
        analysis_types: list[EnrichmentAnalysisType],
        errors: list[str],
    ) -> tuple[list[EnrichmentResult], list[str]]:
        """Run multiple analysis types on a single step concurrently.

        Analyses run in parallel to keep total time under the proxy timeout.
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

        results = list(await asyncio.gather(*[_run_one(t) for t in analysis_types]))
        return results, errors
