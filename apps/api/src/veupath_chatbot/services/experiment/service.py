"""Experiment execution orchestrator.

Coordinates the full experiment lifecycle: evaluation, metrics computation,
optional cross-validation, and optional enrichment analysis.

Each phase is a private function that mutates ``experiment`` and persists
intermediate state to the store.  The public ``run_experiment()`` function
orchestrates phase sequencing, lifecycle management, and error handling.
"""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.cross_validation import run_cross_validation
from veupath_chatbot.services.experiment.enrichment_parser import (
    upsert_enrichment_result,
)
from veupath_chatbot.services.experiment.helpers import (
    ProgressCallback,
    extract_and_enrich_genes,
)
from veupath_chatbot.services.experiment.materialization import (
    _persist_experiment_strategy,
)
from veupath_chatbot.services.experiment.metrics import (
    evaluate_gene_ids_against_controls,
    metrics_from_control_result,
)
from veupath_chatbot.services.experiment.rank_metrics import (
    compute_rank_metrics,
    fetch_ordered_result_ids,
)
from veupath_chatbot.services.experiment.robustness import compute_robustness
from veupath_chatbot.services.experiment.step_analysis import (
    run_controls_against_tree,
    run_step_analysis,
)
from veupath_chatbot.services.experiment.store import (
    ExperimentStore,
    get_experiment_store,
)
from veupath_chatbot.services.experiment.tree_knobs import optimize_tree_knobs
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentProgressPhase,
    OptimizationSpec,
    to_json,
)
from veupath_chatbot.services.gene_sets.operations import (
    _build_enrichment_params_from_gene_ids,
)
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    ParameterSpec,
    optimize_search_parameters,
    result_to_json,
)
from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

logger = get_logger(__name__)

# Type alias for the progress-emit callback threaded through phases.
EmitFn = Callable[..., Awaitable[None]]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _run_single_step_controls(
    config: ExperimentConfig,
    parameters: JSONObject,
) -> JSONObject:
    """Run single-step control tests with the given parameters."""
    return await run_positive_negative_controls(
        site_id=config.site_id,
        record_type=config.record_type,
        target_search_name=config.search_name,
        target_parameters=parameters,
        controls_search_name=config.controls_search_name,
        controls_param_name=config.controls_param_name,
        positive_controls=config.positive_controls or None,
        negative_controls=config.negative_controls or None,
        controls_value_format=config.controls_value_format,
    )


async def _apply_control_result(
    config: ExperimentConfig,
    experiment: Experiment,
    result: JSONObject,
) -> ExperimentMetrics:
    """Compute metrics and populate gene lists from a control-test result."""
    metrics = metrics_from_control_result(result)
    experiment.metrics = metrics
    (
        experiment.true_positive_genes,
        experiment.false_negative_genes,
        experiment.false_positive_genes,
        experiment.true_negative_genes,
    ) = await extract_and_enrich_genes(
        site_id=config.site_id,
        result=result,
        negative_controls=config.negative_controls,
    )
    return metrics


# ---------------------------------------------------------------------------
# Phase functions
# ---------------------------------------------------------------------------


async def _phase_evaluate(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
) -> tuple[JSONObject, ExperimentMetrics]:
    """Run control-test evaluation, compute metrics, and enrich gene lists.

    :returns: ``(control_result, metrics)`` for downstream phases.
    """
    await emit("evaluating", message="Running control tests...")

    if config.target_gene_ids:
        # Gene set mode: evaluate using gene IDs directly, no WDK calls.

        result = evaluate_gene_ids_against_controls(
            gene_ids=config.target_gene_ids,
            positive_controls=config.positive_controls or [],
            negative_controls=config.negative_controls or [],
            site_id=config.site_id,
            record_type=config.record_type,
        )
    elif config.is_tree_mode:
        tree_dict: JSONObject = cast("JSONObject", config.step_tree)
        cvf: ControlValueFormat = config.controls_value_format

        result = await run_controls_against_tree(
            site_id=config.site_id,
            record_type=config.record_type,
            tree=tree_dict,
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            controls_value_format=cvf,
            positive_controls=config.positive_controls or [],
            negative_controls=config.negative_controls or [],
        )
    else:
        result = await _run_single_step_controls(config, config.parameters)

    metrics = await _apply_control_result(config, experiment, result)

    await emit("evaluating", message="Evaluation complete", metrics=to_json(metrics))
    store.save(experiment)

    return result, metrics


async def _phase_step_analysis(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
    tree: JSONObject,
    cvf: ControlValueFormat,
    baseline_result: JSONObject,
    metrics: ExperimentMetrics,
) -> None:
    """Run step-decomposition analysis for multi-step experiments."""

    await emit("step_analysis", message="Running step decomposition analysis...")

    async def _progress(event: JSONObject) -> None:
        data = event.get("data", {})
        msg = data.get("message", "") if isinstance(data, dict) else ""
        await emit("step_analysis", message=str(msg), stepAnalysisProgress=data)

    experiment.step_analysis = await run_step_analysis(
        site_id=config.site_id,
        record_type=config.record_type,
        tree=tree,
        controls_search_name=config.controls_search_name,
        controls_param_name=config.controls_param_name,
        controls_value_format=cvf,
        positive_controls=config.positive_controls or [],
        negative_controls=config.negative_controls or [],
        baseline_result=baseline_result,
        phases=config.step_analysis_phases,
        progress_callback=_progress,
    )
    store.save(experiment)

    await emit(
        "step_analysis", message="Step analysis complete", metrics=to_json(metrics)
    )


async def _phase_persist_strategy(
    config: ExperimentConfig,
    experiment: Experiment,
    store: ExperimentStore,
    final_tree: JSONObject | None,
) -> None:
    """Create a persisted WDK strategy for result exploration (best-effort)."""
    try:
        wdk_ids = await _persist_experiment_strategy(
            config,
            experiment.id,
            override_tree=final_tree,
        )
        raw_sid = wdk_ids.get("strategy_id")
        raw_step = wdk_ids.get("step_id")
        experiment.wdk_strategy_id = raw_sid if isinstance(raw_sid, int) else None
        experiment.wdk_step_id = raw_step if isinstance(raw_step, int) else None
        store.save(experiment)
    except Exception as exc:
        logger.warning(
            "Failed to persist WDK strategy for experiment",
            experiment_id=experiment.id,
            error=str(exc),
        )


async def _phase_rank_metrics(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
) -> list[str]:
    """Compute rank-based metrics when a sort attribute is configured.

    :returns: Ordered result IDs (for downstream robustness phase).
    """
    is_ranked = config.sort_attribute is not None
    if not is_ranked or experiment.wdk_step_id is None:
        return []

    try:
        await emit("evaluating", message="Computing rank-based metrics...")

        ordered_ids = await fetch_ordered_result_ids(
            site_id=config.site_id,
            step_id=experiment.wdk_step_id,
            sort_attribute=config.sort_attribute,
            sort_direction=config.sort_direction,
        )
        if ordered_ids:
            pos_set = set(config.positive_controls or [])
            neg_set = set(config.negative_controls or [])
            experiment.rank_metrics = compute_rank_metrics(
                result_ids=ordered_ids,
                positive_ids=pos_set,
                negative_ids=neg_set,
            )
            store.save(experiment)
    except Exception as exc:
        logger.warning(
            "Rank metrics computation failed",
            experiment_id=experiment.id,
            error=str(exc),
        )
        return []
    else:
        return ordered_ids


async def _phase_robustness(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
    ordered_ids: list[str],
    *,
    is_ranked: bool,
) -> None:
    """Compute bootstrap confidence intervals."""
    if experiment.wdk_step_id is None:
        return

    try:
        await emit("evaluating", message="Computing robustness estimates...")

        if not ordered_ids:
            ordered_ids = await fetch_ordered_result_ids(
                site_id=config.site_id,
                step_id=experiment.wdk_step_id,
            )

        if ordered_ids:
            experiment.robustness = compute_robustness(
                result_ids=ordered_ids,
                positive_ids=config.positive_controls or [],
                negative_ids=config.negative_controls or [],
                n_bootstrap=200,
                include_rank_metrics=is_ranked,
            )
            store.save(experiment)
    except Exception as exc:
        logger.warning(
            "Robustness computation failed",
            experiment_id=experiment.id,
            error=str(exc),
        )


async def _phase_optimize_parameters(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
    metrics: ExperimentMetrics,
) -> tuple[JSONObject | None, ExperimentMetrics]:
    """Run parameter optimization and optionally re-evaluate with best params.

    :returns: ``(updated_result_or_None, updated_metrics)``.
    """

    await emit("evaluating", message="Running parameter optimization...")

    def _spec_optimizable(s: OptimizationSpec) -> bool:
        if s.type == "categorical":
            choices = s.choices or []
            valid = [c for c in choices if isinstance(c, str) and c.strip()]
            return len(valid) > 0
        return True

    optimizable_specs = [
        s for s in (config.optimization_specs or []) if _spec_optimizable(s)
    ]
    optimizable_names = {s.name for s in optimizable_specs}

    if not optimizable_specs:
        logger.info("Skipping parameter optimization: no params with valid space")
        return None, metrics

    opt_param_space = [
        ParameterSpec(
            name=s.name,
            param_type=s.type,
            min_value=s.min,
            max_value=s.max,
            step=s.step,
            choices=s.choices,
        )
        for s in optimizable_specs
    ]

    fixed_params: dict[str, JSONValue] = {
        k: v
        for k, v in config.parameters.items()
        if k not in optimizable_names and v not in ("", None)
    }

    async def _opt_progress(event: JSONObject) -> None:
        trial_data = event.get("data", {})
        trial_num = (
            trial_data.get("currentTrial", "?") if isinstance(trial_data, dict) else "?"
        )
        await emit(
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
            objective=config.optimization_objective,
        ),
        progress_callback=_opt_progress,
    )

    experiment.optimization_result = result_to_json(opt_result)

    if opt_result.best_trial:
        optimized_params = dict(config.parameters)
        optimized_params.update(opt_result.best_trial.parameters)
        await emit(
            "evaluating",
            message="Optimization complete — re-evaluating with best parameters",
        )

        result = await _run_single_step_controls(config, optimized_params)
        metrics = await _apply_control_result(config, experiment, result)
        return result, metrics

    return None, metrics


async def _phase_optimize_tree_knobs(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
    tree: JSONObject,
    cvf: ControlValueFormat,
) -> None:
    """Optimize threshold parameters and boolean operators across a strategy tree."""
    try:
        await emit("optimizing", message="Optimizing strategy tree knobs...")

        tree_opt_result = await optimize_tree_knobs(
            site_id=config.site_id,
            record_type=config.record_type,
            base_tree=tree,
            threshold_knobs=config.threshold_knobs or [],
            operator_knobs=config.operator_knobs or [],
            positive_controls=config.positive_controls or [],
            negative_controls=config.negative_controls or [],
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            controls_value_format=cvf,
            objective=config.tree_optimization_objective,
            budget=config.tree_optimization_budget,
            max_list_size=config.max_list_size,
        )
        experiment.tree_optimization = tree_opt_result
        store.save(experiment)
        await emit(
            "optimizing",
            message=f"Tree optimization complete — best score: {tree_opt_result.best_trial.score:.4f}"
            if tree_opt_result.best_trial
            else "Tree optimization complete — no improving trial found",
        )
    except Exception as exc:
        logger.warning(
            "Tree knob optimization failed",
            experiment_id=experiment.id,
            error=str(exc),
        )


async def _phase_cross_validate(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
    *,
    metrics: ExperimentMetrics,
    final_tree: JSONObject | None,
    cvf: ControlValueFormat,
) -> None:
    """Run k-fold cross-validation (tree or single-step)."""
    await emit(
        "cross_validating",
        message=f"Running {config.k_folds}-fold cross-validation...",
    )

    async def _cv_progress(fold_idx: int, total: int) -> None:
        await emit(
            "cross_validating",
            message=f"Fold {fold_idx + 1} of {total}",
            cvFoldIndex=fold_idx,
            cvTotalFolds=total,
        )

    experiment.cross_validation = await run_cross_validation(
        site_id=config.site_id,
        record_type=config.record_type,
        controls_search_name=config.controls_search_name,
        controls_param_name=config.controls_param_name,
        controls_value_format=cvf,
        positive_controls=config.positive_controls,
        negative_controls=config.negative_controls,
        tree=final_tree,
        search_name=config.search_name if final_tree is None else None,
        parameters=config.parameters if final_tree is None else None,
        k=config.k_folds,
        full_metrics=metrics,
        progress_callback=_cv_progress,
    )
    store.save(experiment)


async def _phase_enrich(
    config: ExperimentConfig,
    experiment: Experiment,
    emit: EmitFn,
    store: ExperimentStore,
) -> None:
    """Run enrichment analyses on experiment results."""

    await emit("enriching", message="Running enrichment analyses...")

    step_id = experiment.wdk_step_id
    search_name = config.search_name
    record_type = config.record_type
    parameters = config.parameters

    # Gene-ID experiments may lack a WDK step and search_name.
    # Build a temporary GeneByLocusTag dataset so enrichment can proceed.
    if step_id is None and not search_name and config.target_gene_ids:
        (
            search_name,
            parameters,
            record_type,
        ) = await _build_enrichment_params_from_gene_ids(
            config.site_id, config.target_gene_ids
        )

    svc = EnrichmentService()
    enrich_results, _ = await svc.run_batch(
        site_id=config.site_id,
        analysis_types=config.enrichment_types,
        step_id=step_id,
        search_name=search_name,
        record_type=record_type,
        parameters=parameters,
    )
    for enrich_result in enrich_results:
        upsert_enrichment_result(experiment.enrichment_results, enrich_result)
    store.save(experiment)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_experiment(
    config: ExperimentConfig,
    *,
    user_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Experiment:
    """Execute a full experiment and persist the result.

    :param config: Experiment configuration.
    :param user_id: Owning user ID (for IDOR protection).
    :param progress_callback: Optional async callback for SSE progress events.
    :returns: Completed experiment with all results.
    """
    experiment_id = f"exp_{uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()
    store = get_experiment_store()

    experiment = Experiment(
        id=experiment_id,
        config=config,
        user_id=user_id,
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
                    **cast("JSONObject", dict(extra)),
                },
            }
            await progress_callback(event)

    try:
        await _emit("started", message="Starting evaluation...")

        # Phase 1: Control-test evaluation + metrics + gene enrichment
        result, metrics = await _phase_evaluate(config, experiment, _emit, store)

        tree_dict: JSONObject = (
            cast("JSONObject", config.step_tree) if config.is_tree_mode else {}
        )
        cvf: ControlValueFormat = config.controls_value_format
        final_tree: JSONObject | None = tree_dict if config.is_tree_mode else None

        # Phase 2: Step analysis (multi-step only)
        if config.is_tree_mode and config.enable_step_analysis:
            await _phase_step_analysis(
                config,
                experiment,
                _emit,
                store,
                tree_dict,
                cvf,
                result,
                metrics,
            )

        # Phase 3: Persist WDK strategy for result exploration
        await _phase_persist_strategy(config, experiment, store, final_tree)

        # Phase 4: Rank-based metrics
        is_ranked = config.sort_attribute is not None
        ordered_ids = await _phase_rank_metrics(config, experiment, _emit, store)

        # Phase 5: Robustness / bootstrap CIs
        await _phase_robustness(
            config,
            experiment,
            _emit,
            store,
            ordered_ids,
            is_ranked=is_ranked,
        )

        # Phase 6: Parameter optimization (single-step only)
        if (
            not config.is_tree_mode
            and config.optimization_specs
            and len(config.optimization_specs) > 0
        ):
            _, metrics = await _phase_optimize_parameters(
                config,
                experiment,
                _emit,
                store,
                metrics,
            )

        # Phase 7: Tree-knob optimization (multi-step only)
        has_tree_knobs = bool(config.threshold_knobs or config.operator_knobs)
        if config.is_tree_mode and has_tree_knobs and final_tree is not None:
            await _phase_optimize_tree_knobs(
                config, experiment, _emit, store, tree_dict, cvf
            )

        # Phase 8: Cross-validation
        if (
            config.enable_cross_validation
            and config.positive_controls
            and config.negative_controls
        ):
            await _phase_cross_validate(
                config,
                experiment,
                _emit,
                store,
                metrics=metrics,
                final_tree=final_tree,
                cvf=cvf,
            )

        # Phase 9: Enrichment analysis
        if config.enrichment_types:
            await _phase_enrich(config, experiment, _emit, store)

        # Finalize
        experiment.status = "completed"
        experiment.total_time_seconds = time.monotonic() - start
        experiment.completed_at = datetime.now(UTC).isoformat()
        store.save(experiment)

        await _emit("completed", message="Experiment complete")

    except Exception as exc:
        experiment.status = "error"
        experiment.error = str(exc)
        experiment.total_time_seconds = time.monotonic() - start
        store.save(experiment)
        await _emit("error", error=str(exc))
        raise
    else:
        return experiment
