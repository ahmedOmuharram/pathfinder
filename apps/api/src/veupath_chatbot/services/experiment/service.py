"""Experiment execution orchestrator.

Coordinates the full experiment lifecycle: evaluation, metrics computation,
optional cross-validation, and optional enrichment analysis.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.cross_validation import (
    run_cross_validation,
    run_cross_validation_tree,
)
from veupath_chatbot.services.experiment.enrichment import run_enrichment_analysis
from veupath_chatbot.services.experiment.helpers import (
    ProgressCallback,
    _extract_gene_list,
    _extract_id_set,
)
from veupath_chatbot.services.experiment.materialization import (
    _persist_experiment_strategy,
)
from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    Experiment,
    ExperimentConfig,
    ExperimentProgressPhase,
    OptimizationSpec,
    metrics_to_json,
)

logger = get_logger(__name__)


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
                    **cast(JSONObject, dict(extra)),
                },
            }
            await progress_callback(event)

    try:
        await _emit("started", message="Starting evaluation...")
        mode = config.mode or "single"
        is_tree_mode = mode in ("multi-step", "import") and isinstance(
            config.step_tree, dict
        )

        # --- Phase 1: Run control test evaluation ---
        await _emit("evaluating", message="Running control tests...")

        if is_tree_mode:
            from veupath_chatbot.services.experiment.step_analysis import (
                run_controls_against_tree,
            )

            tree_dict: JSONObject = cast(JSONObject, config.step_tree)
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

        # --- Phase 1b: Step Analysis (multi-step / import) ---
        final_tree = tree_dict if is_tree_mode else None

        if is_tree_mode and config.enable_step_analysis:
            from veupath_chatbot.services.experiment.step_analysis import (
                run_step_analysis,
            )

            await _emit(
                "step_analysis", message="Running step decomposition analysis..."
            )

            async def _step_analysis_progress(event: JSONObject) -> None:
                data = event.get("data", {})
                msg = data.get("message", "") if isinstance(data, dict) else ""
                await _emit(
                    "step_analysis", message=str(msg), stepAnalysisProgress=data
                )

            step_analysis_result = await run_step_analysis(
                site_id=config.site_id,
                record_type=config.record_type,
                tree=tree_dict,
                controls_search_name=config.controls_search_name,
                controls_param_name=config.controls_param_name,
                controls_value_format=cvf,
                positive_controls=config.positive_controls or [],
                negative_controls=config.negative_controls or [],
                baseline_result=result,
                phases=config.step_analysis_phases,
                progress_callback=_step_analysis_progress,
            )
            experiment.step_analysis = step_analysis_result

            await _emit(
                "step_analysis",
                message="Step analysis complete",
                metrics=metrics_to_json(metrics),
            )

        # --- Persist a WDK strategy for result exploration ---
        try:
            persist_tree = final_tree if is_tree_mode else None
            wdk_ids = await _persist_experiment_strategy(
                config,
                experiment_id,
                override_tree=persist_tree,
            )
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

        # --- Phase 1c: Rank-based metrics (only when ranking is configured) ---
        is_ranked = config.sort_attribute is not None
        ordered_ids: list[str] = []
        if is_ranked and experiment.wdk_step_id is not None:
            try:
                await _emit("evaluating", message="Computing rank-based metrics...")
                from veupath_chatbot.services.experiment.rank_metrics import (
                    compute_rank_metrics,
                    fetch_ordered_result_ids,
                )

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
            except Exception as exc:
                logger.warning(
                    "Rank metrics computation failed",
                    experiment_id=experiment_id,
                    error=str(exc),
                )

        # --- Phase 1d: Robustness / bootstrap CIs ---
        if experiment.wdk_step_id is not None:
            try:
                await _emit("evaluating", message="Computing robustness estimates...")
                from veupath_chatbot.services.experiment.robustness import (
                    compute_robustness,
                )

                if not ordered_ids:
                    from veupath_chatbot.services.experiment.rank_metrics import (
                        fetch_ordered_result_ids as _fetch_ids,
                    )

                    ordered_ids = await _fetch_ids(
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
            except Exception as exc:
                logger.warning(
                    "Robustness computation failed",
                    experiment_id=experiment_id,
                    error=str(exc),
                )

        # --- Phase 1b (single-step): Parameter optimization ---
        if (
            not is_tree_mode
            and config.optimization_specs
            and len(config.optimization_specs) > 0
        ):
            from veupath_chatbot.services.parameter_optimization import (
                OptimizationConfig,
                optimize_search_parameters,
                result_to_json,
            )
            from veupath_chatbot.services.parameter_optimization import (
                ParameterSpec as OptParamSpec,
            )

            await _emit("evaluating", message="Running parameter optimization...")

            def _spec_optimizable(s: OptimizationSpec) -> bool:
                if s.type == "categorical":
                    choices = s.choices or []
                    valid = [c for c in choices if isinstance(c, str) and c.strip()]
                    return len(valid) > 0
                return True

            optimizable_specs = [
                s for s in config.optimization_specs if _spec_optimizable(s)
            ]
            optimizable_names = {s.name for s in optimizable_specs}

            if not optimizable_specs:
                logger.info(
                    "Skipping parameter optimization: no params with valid space",
                )
            else:
                opt_param_space = [
                    OptParamSpec(
                        name=s.name,
                        param_type=s.type,
                        min_value=s.min,
                        max_value=s.max,
                        step=s.step,
                        choices=s.choices,
                    )
                    for s in optimizable_specs
                ]

                fixed_params = {
                    k: v
                    for k, v in config.parameters.items()
                    if k not in optimizable_names and v not in ("", None)
                }

                async def _opt_progress(event: JSONObject) -> None:
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
                        objective=config.optimization_objective,
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

        # --- Phase 1e: Tree-knob optimization (multi-step) ---
        has_tree_knobs = bool(config.threshold_knobs or config.operator_knobs)
        if is_tree_mode and has_tree_knobs and tree_dict is not None:
            try:
                await _emit("optimizing", message="Optimizing strategy tree knobs...")
                from veupath_chatbot.services.experiment.tree_knobs import (
                    optimize_tree_knobs,
                )

                tree_opt_result = await optimize_tree_knobs(
                    site_id=config.site_id,
                    record_type=config.record_type,
                    base_tree=tree_dict,
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
                await _emit(
                    "optimizing",
                    message=f"Tree optimization complete — best score: {tree_opt_result.best_trial.score:.4f}"
                    if tree_opt_result.best_trial
                    else "Tree optimization complete — no improving trial found",
                )
            except Exception as exc:
                logger.warning(
                    "Tree knob optimization failed",
                    experiment_id=experiment_id,
                    error=str(exc),
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

            if is_tree_mode and final_tree is not None:
                cv_result = await run_cross_validation_tree(
                    site_id=config.site_id,
                    record_type=config.record_type,
                    tree=final_tree,
                    controls_search_name=config.controls_search_name,
                    controls_param_name=config.controls_param_name,
                    controls_value_format=cvf,
                    positive_controls=config.positive_controls,
                    negative_controls=config.negative_controls,
                    k=config.k_folds,
                    full_metrics=metrics,
                    progress_callback=cv_progress,
                )
            else:
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
        enrich_search = config.search_name
        enrich_params = config.parameters
        for enrich_type in config.enrichment_types:
            await _emit(
                "enriching",
                message=f"Running {enrich_type} enrichment...",
                enrichmentType=enrich_type,
            )
            try:
                if is_tree_mode and experiment.wdk_step_id is not None:
                    from veupath_chatbot.services.experiment.enrichment import (
                        run_enrichment_on_step,
                    )

                    enrich_result = await run_enrichment_on_step(
                        site_id=config.site_id,
                        step_id=experiment.wdk_step_id,
                        analysis_type=enrich_type,
                    )
                else:
                    enrich_result = await run_enrichment_analysis(
                        site_id=config.site_id,
                        record_type=config.record_type,
                        search_name=enrich_search,
                        parameters=enrich_params,
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
