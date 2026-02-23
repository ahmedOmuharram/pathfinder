"""Experiment execution orchestrator.

Coordinates the full experiment lifecycle: evaluation, metrics computation,
optional cross-validation, and optional enrichment analysis.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.cross_validation import run_cross_validation
from veupath_chatbot.services.experiment.enrichment import run_enrichment_analysis
from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    ExperimentProgressPhase,
    GeneInfo,
    metrics_to_json,
)

logger = get_logger(__name__)

ProgressCallback = Callable[[JSONObject], Awaitable[None]]
"""Emits an SSE-friendly progress event dict."""


async def run_experiment(
    config: ExperimentConfig,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Experiment:
    """Execute a full experiment and persist the result.

    :param config: Experiment configuration.
    :param progress_callback: Optional async callback for SSE progress events.
    :returns: Completed experiment with all results.
    """
    experiment_id = f"exp_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    store = get_experiment_store()

    experiment = Experiment(
        id=experiment_id,
        config=config,
        status="running",
        created_at=now,
    )
    store.save(experiment)

    start = time.monotonic()

    async def _emit(phase: ExperimentProgressPhase, **extra: object) -> None:
        if progress_callback:
            event: JSONObject = {
                "type": "experiment_progress",
                "data": {
                    "experimentId": experiment_id,
                    "phase": phase,
                    **dict(extra),
                },
            }
            await progress_callback(event)

    try:
        await _emit("started", message="Starting evaluation...")

        # --- Phase 1: Run control test evaluation ---
        await _emit("evaluating", message="Running control tests...")

        result = await run_positive_negative_controls(
            site_id=config.site_id,
            record_type=config.record_type,
            target_search_name=config.search_name,
            target_parameters=config.parameters,
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            positive_controls=config.positive_controls or None,
            negative_controls=config.negative_controls or None,
            controls_value_format=config.controls_value_format,
        )

        metrics = metrics_from_control_result(result)
        experiment.metrics = metrics

        experiment.true_positive_genes = _extract_gene_list(
            result, "positive", "intersectionIds"
        )
        experiment.false_negative_genes = _extract_gene_list(
            result, "positive", "missingIdsSample"
        )
        experiment.false_positive_genes = _extract_gene_list(
            result, "negative", "intersectionIds"
        )
        experiment.true_negative_genes = _extract_gene_list(
            result,
            "negative",
            "missingIdsSample",
            fallback_from_controls=True,
            all_controls=config.negative_controls,
            hit_ids=_extract_id_set(result, "negative", "intersectionIds"),
        )

        await _emit(
            "evaluating",
            message="Evaluation complete",
            metrics=metrics_to_json(metrics),
        )

        # --- Phase 2: Cross-validation (optional) ---
        if (
            config.enable_cross_validation
            and config.positive_controls
            and config.negative_controls
        ):
            await _emit(
                "cross_validating",
                message=f"Running {config.k_folds}-fold cross-validation...",
            )

            async def cv_progress(fold_idx: int, total: int) -> None:
                await _emit(
                    "cross_validating",
                    message=f"Fold {fold_idx + 1} of {total}",
                    cvFoldIndex=fold_idx,
                    cvTotalFolds=total,
                )

            cv_result = await run_cross_validation(
                site_id=config.site_id,
                record_type=config.record_type,
                search_name=config.search_name,
                parameters=config.parameters,
                controls_search_name=config.controls_search_name,
                controls_param_name=config.controls_param_name,
                positive_controls=config.positive_controls,
                negative_controls=config.negative_controls,
                controls_value_format=config.controls_value_format,
                k=config.k_folds,
                full_metrics=metrics,
                progress_callback=cv_progress,
            )
            experiment.cross_validation = cv_result

        # --- Phase 3: Enrichment analysis (optional) ---
        for enrich_type in config.enrichment_types:
            await _emit(
                "enriching",
                message=f"Running {enrich_type} enrichment...",
                enrichmentType=enrich_type,
            )
            try:
                enrich_result = await run_enrichment_analysis(
                    site_id=config.site_id,
                    record_type=config.record_type,
                    search_name=config.search_name,
                    parameters=config.parameters,
                    analysis_type=enrich_type,
                )
                experiment.enrichment_results.append(enrich_result)
            except Exception as exc:
                logger.warning(
                    "Enrichment analysis failed",
                    analysis_type=enrich_type,
                    error=str(exc),
                )

        experiment.status = "completed"
        experiment.total_time_seconds = time.monotonic() - start
        experiment.completed_at = datetime.now(UTC).isoformat()
        store.save(experiment)

        await _emit("completed", message="Experiment complete")
        return experiment

    except Exception as exc:
        experiment.status = "error"
        experiment.error = str(exc)
        experiment.total_time_seconds = time.monotonic() - start
        store.save(experiment)
        await _emit("error", error=str(exc))
        raise


def _extract_gene_list(
    result: JSONObject,
    section: str,
    key: str,
    *,
    fallback_from_controls: bool = False,
    all_controls: list[str] | None = None,
    hit_ids: set[str] | None = None,
) -> list[GeneInfo]:
    """Extract a gene ID list from control-test result and wrap as GeneInfo."""
    section_data = result.get(section)
    if not isinstance(section_data, dict):
        if fallback_from_controls and all_controls and hit_ids is not None:
            return [GeneInfo(id=g) for g in all_controls if g not in hit_ids]
        return []

    ids_raw = section_data.get(key)
    if isinstance(ids_raw, list):
        return [GeneInfo(id=str(g)) for g in ids_raw if g is not None]

    if fallback_from_controls and all_controls and hit_ids is not None:
        return [GeneInfo(id=g) for g in all_controls if g not in hit_ids]
    return []


def _extract_id_set(
    result: JSONObject,
    section: str,
    key: str,
) -> set[str]:
    """Extract a set of IDs from a control-test result section."""
    section_data = result.get(section)
    if not isinstance(section_data, dict):
        return set()
    ids_raw = section_data.get(key)
    if isinstance(ids_raw, list):
        return {str(g) for g in ids_raw if g is not None}
    return set()
