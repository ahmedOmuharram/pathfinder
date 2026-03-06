"""Unified enrichment service.

Single entry point for running enrichment analyses regardless of
whether the caller is an experiment endpoint, gene set endpoint,
or AI tool.
"""

from __future__ import annotations

import asyncio

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.enrichment import (
    run_enrichment_analysis,
    run_enrichment_on_step,
)
from veupath_chatbot.services.experiment.types import (
    EnrichmentAnalysisType,
    EnrichmentResult,
)

logger = get_logger(__name__)


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
        if step_id is not None:
            return await run_enrichment_on_step(
                site_id=site_id,
                step_id=step_id,
                analysis_type=analysis_type,
            )
        if search_name and parameters is not None:
            return await run_enrichment_analysis(
                site_id=site_id,
                record_type=record_type or "gene",
                search_name=search_name,
                parameters=parameters,
                analysis_type=analysis_type,
            )
        raise ValueError("Either step_id or search_name+parameters required")

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
        """Run multiple enrichment analyses concurrently, collecting results and errors."""
        results: list[EnrichmentResult] = []
        errors: list[str] = []

        async def _run_one(analysis_type: EnrichmentAnalysisType) -> EnrichmentResult:
            try:
                return await self.run(
                    site_id=site_id,
                    step_id=step_id,
                    analysis_type=analysis_type,
                    search_name=search_name,
                    record_type=record_type,
                    parameters=parameters,
                )
            except Exception as exc:
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

        results = list(await asyncio.gather(*[_run_one(at) for at in analysis_types]))
        return results, errors
