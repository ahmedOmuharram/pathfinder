"""Experiment execution orchestrator.

Coordinates the full experiment lifecycle: evaluation, metrics computation,
optional cross-validation, and optional enrichment analysis.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode
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

        # --- Persist a WDK strategy for result exploration ---
        try:
            wdk_ids = await _persist_experiment_strategy(config, experiment_id)
            raw_sid = wdk_ids.get("strategy_id")
            raw_step = wdk_ids.get("step_id")
            experiment.wdk_strategy_id = raw_sid if isinstance(raw_sid, int) else None
            experiment.wdk_step_id = raw_step if isinstance(raw_step, int) else None
        except Exception as exc:
            logger.warning(
                "Failed to persist WDK strategy for experiment",
                experiment_id=experiment_id,
                error=str(exc),
            )

        # --- Phase 1b: Parameter optimization (optional) ---
        if config.optimization_specs and len(config.optimization_specs) > 0:
            from veupath_chatbot.services.parameter_optimization import (
                OptimizationConfig,
                optimize_search_parameters,
                result_to_json,
            )
            from veupath_chatbot.services.parameter_optimization import (
                ParameterSpec as OptParamSpec,
            )

            await _emit("evaluating", message="Running parameter optimization...")

            opt_param_space = [
                OptParamSpec(
                    name=s.name,
                    param_type=s.type,  # type: ignore[arg-type]
                    min_value=s.min,
                    max_value=s.max,
                    step=s.step,
                    choices=s.choices,
                )
                for s in config.optimization_specs
            ]

            fixed_params = {
                k: v
                for k, v in config.parameters.items()
                if not any(s.name == k for s in config.optimization_specs)
                and v not in ("", None)
            }

            async def _opt_progress(event: JSONObject) -> None:
                """Bridge optimization_progress events into experiment_progress."""
                trial_data = event.get("data", {})
                trial_num = (
                    trial_data.get("currentTrial", "?")
                    if isinstance(trial_data, dict)
                    else "?"
                )
                await _emit(
                    "optimizing",
                    message=f"Trial {trial_num} / {config.optimization_budget}",
                    trialProgress=event.get("data"),
                )

            opt_result = await optimize_search_parameters(
                site_id=config.site_id,
                record_type=config.record_type,
                search_name=config.search_name,
                fixed_parameters=fixed_params,
                parameter_space=opt_param_space,
                controls_search_name=config.controls_search_name,
                controls_param_name=config.controls_param_name,
                positive_controls=config.positive_controls or None,
                negative_controls=config.negative_controls or None,
                controls_value_format=config.controls_value_format,
                config=OptimizationConfig(
                    budget=config.optimization_budget,
                    objective=config.optimization_objective,  # type: ignore[arg-type]
                ),
                progress_callback=_opt_progress,
            )

            experiment.optimization_result = result_to_json(opt_result)

            if opt_result.best_trial:
                optimized_params = dict(config.parameters)
                optimized_params.update(opt_result.best_trial.parameters)
                experiment.metrics = metrics
                await _emit(
                    "evaluating",
                    message="Optimization complete — re-evaluating with best parameters",
                )

                result = await run_positive_negative_controls(
                    site_id=config.site_id,
                    record_type=config.record_type,
                    target_search_name=config.search_name,
                    target_parameters=optimized_params,
                    controls_search_name=config.controls_search_name,
                    controls_param_name=config.controls_param_name,
                    positive_controls=config.positive_controls or None,
                    negative_controls=config.negative_controls or None,
                    controls_value_format=config.controls_value_format,
                )
                metrics = metrics_from_control_result(result)
                experiment.metrics = metrics

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


async def _persist_experiment_strategy(
    config: ExperimentConfig,
    experiment_id: str,
) -> JSONObject:
    """Create a persisted WDK strategy for result exploration.

    This strategy survives the experiment run and enables downstream
    features like result table browsing, step analyses, and interactive
    filtering.

    :param config: Experiment configuration.
    :param experiment_id: Unique experiment identifier.
    :returns: Dict with ``strategy_id`` and ``step_id``.
    """
    api = get_strategy_api(config.site_id)

    step_payload = await api.create_step(
        record_type=config.record_type,
        search_name=config.search_name,
        parameters=config.parameters or {},
        custom_name=f"Experiment: {config.name}",
    )
    step_id: int | None = None
    if isinstance(step_payload, dict):
        raw = step_payload.get("id")
        if isinstance(raw, int):
            step_id = raw
    if step_id is None:
        raise ValueError("Failed to create WDK step for experiment strategy")

    root = StepTreeNode(step_id)
    created = await api.create_strategy(
        step_tree=root,
        name=f"exp:{experiment_id}",
        description=f"Persisted strategy for experiment {config.name}",
        is_internal=True,
    )
    strategy_id: int | None = None
    if isinstance(created, dict):
        raw = created.get("id")
        if isinstance(raw, int):
            strategy_id = raw
    if strategy_id is None:
        raise ValueError("Failed to create WDK strategy for experiment")

    logger.info(
        "Persisted WDK strategy for experiment",
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        step_id=step_id,
    )
    return {"strategy_id": strategy_id, "step_id": step_id}


async def cleanup_experiment_strategy(experiment: Experiment) -> None:
    """Delete the persisted WDK strategy when an experiment is deleted.

    :param experiment: Experiment whose WDK strategy should be cleaned up.
    """
    if experiment.wdk_strategy_id is None:
        return
    try:
        api = get_strategy_api(experiment.config.site_id)
        await api.delete_strategy(experiment.wdk_strategy_id)
        logger.info(
            "Deleted WDK strategy for experiment",
            experiment_id=experiment.id,
            strategy_id=experiment.wdk_strategy_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to delete WDK strategy during experiment cleanup",
            experiment_id=experiment.id,
            strategy_id=experiment.wdk_strategy_id,
            error=str(exc),
        )
