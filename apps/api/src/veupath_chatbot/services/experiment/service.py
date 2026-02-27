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
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StepTreeNode,
    StrategyAPI,
)
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
    OptimizationSpec,
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
        mode = config.mode or "single"
        is_tree_mode = mode in ("multi-step", "import") and isinstance(
            config.step_tree, dict
        )

        # --- Phase 1: Run control test evaluation ---
        await _emit("evaluating", message="Running control tests...")

        if is_tree_mode:
            from veupath_chatbot.services.control_tests import ControlValueFormat
            from veupath_chatbot.services.experiment.tree_optimization import (
                TreeOptimizationConfig,
                optimize_strategy_tree,
                run_controls_against_tree,
                tree_optimization_result_to_json,
            )

            tree_dict: JSONObject = config.step_tree  # type: ignore[assignment]
            cvf: ControlValueFormat = config.controls_value_format  # type: ignore[assignment]

            result = await run_controls_against_tree(
                site_id=config.site_id,
                record_type=config.record_type,
                tree=tree_dict,
                controls_search_name=config.controls_search_name,
                controls_param_name=config.controls_param_name,
                controls_value_format=cvf,
                positive_controls=config.positive_controls or None,
                negative_controls=config.negative_controls or None,
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

        # --- Phase 1b: Tree-level optimisation (multi-step / import) ---
        final_tree = tree_dict if is_tree_mode else None
        if is_tree_mode and config.enable_tree_optimization:
            await _emit("optimizing", message="Running tree optimisation...")

            async def _tree_opt_progress(event: JSONObject) -> None:
                data = event.get("data", {})
                msg = data.get("message", "") if isinstance(data, dict) else ""
                await _emit("optimizing", message=str(msg), trialProgress=data)

            tree_opt_result = await optimize_strategy_tree(
                site_id=config.site_id,
                record_type=config.record_type,
                tree=tree_dict,
                controls_search_name=config.controls_search_name,
                controls_param_name=config.controls_param_name,
                controls_value_format=cvf,
                positive_controls=config.positive_controls or None,
                negative_controls=config.negative_controls or None,
                config=TreeOptimizationConfig(
                    budget=config.tree_optimization_budget,
                    objective=config.optimization_objective or "balanced_accuracy",
                    optimize_operators=config.optimize_operators,
                    optimize_orthologs=config.optimize_orthologs,
                    ortholog_organisms=config.ortholog_organisms or [],
                    optimize_structure=config.optimize_structure,
                ),
                progress_callback=_tree_opt_progress,
            )

            experiment.optimized_tree = tree_opt_result.best_tree
            experiment.tree_optimization_diff = tree_optimization_result_to_json(
                tree_opt_result
            )

            if tree_opt_result.best_metrics:
                metrics = tree_opt_result.best_metrics
                experiment.metrics = metrics

            if isinstance(tree_opt_result.best_tree, dict):
                final_tree = tree_opt_result.best_tree

            await _emit(
                "evaluating",
                message="Tree optimisation complete",
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
                        param_type=s.type,  # type: ignore[arg-type]
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


def _coerce_step_id(payload: JSONObject | None) -> int:
    """Extract step ID from a WDK step-creation response."""
    if isinstance(payload, dict):
        raw = payload.get("id")
        if isinstance(raw, int):
            return raw
    raise ValueError("Failed to extract step ID from WDK response")


async def _materialize_step_tree(
    api: StrategyAPI,
    node: JSONObject,
    record_type: str,
) -> StepTreeNode:
    """Recursively create WDK steps from a ``PlanStepNode`` dict.

    Walks the tree bottom-up: leaf search nodes are created first,
    then combine/transform nodes reference them.

    :param api: Strategy API instance.
    :param node: ``PlanStepNode``-shaped dict.
    :param record_type: WDK record type for all steps.
    :returns: :class:`StepTreeNode` ready for strategy creation.
    """
    primary_node = node.get("primaryInput")
    secondary_node = node.get("secondaryInput")

    primary_tree: StepTreeNode | None = None
    secondary_tree: StepTreeNode | None = None

    if isinstance(primary_node, dict):
        primary_tree = await _materialize_step_tree(api, primary_node, record_type)
    if isinstance(secondary_node, dict):
        secondary_tree = await _materialize_step_tree(api, secondary_node, record_type)

    search_name = str(node.get("searchName", ""))
    raw_params = node.get("parameters")
    parameters: JSONObject = raw_params if isinstance(raw_params, dict) else {}
    display_name = str(node.get("displayName", search_name))

    if primary_tree is not None and secondary_tree is not None:
        operator = str(node.get("operator", "INTERSECT"))
        step = await api.create_combined_step(
            primary_step_id=primary_tree.step_id,
            secondary_step_id=secondary_tree.step_id,
            boolean_operator=operator,
            record_type=record_type,
            custom_name=display_name,
        )
        step_id = _coerce_step_id(step)
        return StepTreeNode(
            step_id, primary_input=primary_tree, secondary_input=secondary_tree
        )
    elif primary_tree is not None:
        step = await api.create_transform_step(
            input_step_id=primary_tree.step_id,
            transform_name=search_name,
            parameters=parameters,
            record_type=record_type,
            custom_name=display_name,
        )
        step_id = _coerce_step_id(step)
        return StepTreeNode(step_id, primary_input=primary_tree)
    else:
        step = await api.create_step(
            record_type=record_type,
            search_name=search_name,
            parameters=parameters,
            custom_name=display_name,
        )
        step_id = _coerce_step_id(step)
        return StepTreeNode(step_id)


async def _persist_experiment_strategy(
    config: ExperimentConfig,
    experiment_id: str,
    *,
    override_tree: JSONObject | None = None,
) -> JSONObject:
    """Create a persisted WDK strategy for result exploration.

    Handles all experiment modes:

    * **single**: one search step.
    * **multi-step**: recursively materialise the ``step_tree``.
    * **import**: duplicate the step tree from an existing WDK strategy.

    :param config: Experiment configuration.
    :param experiment_id: Unique experiment identifier.
    :param override_tree: If provided, materialise this tree instead of the
        config's ``step_tree`` (used after tree optimisation).
    :returns: Dict with ``strategy_id`` and ``step_id``.
    """
    api = get_strategy_api(config.site_id)
    mode = config.mode or "single"

    if mode == "import" and config.source_strategy_id and override_tree is None:
        return await _persist_import_strategy(api, config, experiment_id)

    effective_tree = override_tree or (
        config.step_tree if isinstance(config.step_tree, dict) else None
    )
    if mode in ("multi-step", "import") and isinstance(effective_tree, dict):
        root_tree = await _materialize_step_tree(
            api, effective_tree, config.record_type
        )
    else:
        step_payload = await api.create_step(
            record_type=config.record_type,
            search_name=config.search_name,
            parameters=config.parameters or {},
            custom_name=f"Experiment: {config.name}",
        )
        step_id = _coerce_step_id(step_payload)
        root_tree = StepTreeNode(step_id)

    created = await api.create_strategy(
        step_tree=root_tree,
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
        step_id=root_tree.step_id,
    )
    return {"strategy_id": strategy_id, "step_id": root_tree.step_id}


async def _persist_import_strategy(
    api: StrategyAPI,
    config: ExperimentConfig,
    experiment_id: str,
) -> JSONObject:
    """Import an existing WDK strategy by duplicating its step tree.

    Uses the WDK ``duplicated-step-tree`` endpoint to copy the source
    strategy's step tree into a new set of unattached steps.

    :param api: Strategy API instance.
    :param config: Experiment configuration (must have ``source_strategy_id``).
    :param experiment_id: Unique experiment identifier.
    :returns: Dict with ``strategy_id`` and ``step_id``.
    """
    if not config.source_strategy_id:
        raise ValueError("source_strategy_id is required for import mode")
    source_id = int(config.source_strategy_id)

    # WDK POST .../duplicated-step-tree returns {"stepTree": {...}}
    dup_resp = await api.client.post(
        f"/users/{api.user_id}/strategies/{source_id}/duplicated-step-tree"
    )
    if not isinstance(dup_resp, dict) or "stepTree" not in dup_resp:
        raise ValueError(f"Failed to duplicate step tree from strategy {source_id}")

    raw_tree: JSONObject = dup_resp["stepTree"]  # type: ignore[assignment]

    # The duplicated tree already has real WDK step IDs, so we can
    # directly wrap it in a StepTreeNode.
    def _tree_to_node(t: JSONObject) -> StepTreeNode:
        raw_sid = t["stepId"]
        if isinstance(raw_sid, int):
            sid = raw_sid
        elif isinstance(raw_sid, (str, float)):
            sid = int(raw_sid)
        else:
            raise ValueError(f"Invalid stepId type: {type(raw_sid)}")
        primary = t.get("primaryInput")
        secondary = t.get("secondaryInput")
        return StepTreeNode(
            sid,
            primary_input=_tree_to_node(primary) if isinstance(primary, dict) else None,
            secondary_input=_tree_to_node(secondary)
            if isinstance(secondary, dict)
            else None,
        )

    root = _tree_to_node(raw_tree)

    created = await api.create_strategy(
        step_tree=root,
        name=f"exp:{experiment_id}",
        description=f"Imported strategy for experiment {config.name}",
        is_internal=True,
    )
    strategy_id: int | None = None
    if isinstance(created, dict):
        raw = created.get("id")
        if isinstance(raw, int):
            strategy_id = raw
    if strategy_id is None:
        raise ValueError("Failed to create WDK strategy from imported tree")

    logger.info(
        "Persisted imported WDK strategy for experiment",
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        step_id=root.step_id,
    )
    return {"strategy_id": strategy_id, "step_id": root.step_id}


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
