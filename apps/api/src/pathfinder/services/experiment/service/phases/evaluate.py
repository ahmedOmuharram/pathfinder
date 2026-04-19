"""Evaluation phases: control-test evaluation, step analysis, strategy
persistence, and rank-based metrics.

These phases run early in the experiment lifecycle to establish baseline
metrics and persist WDK artifacts.
"""

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.helpers import ControlsContext
from pathfinder.services.experiment.materialization import (
    _persist_experiment_strategy,
)
from pathfinder.services.experiment.metrics import (
    evaluate_gene_ids_against_controls,
)
from pathfinder.services.experiment.rank_metrics import (
    compute_rank_metrics,
    fetch_ordered_result_ids,
)
from pathfinder.services.experiment.service.context import PhaseContext
from pathfinder.services.experiment.service.shared import (
    apply_control_result,
    run_single_step_controls,
)
from pathfinder.services.experiment.step_analysis import (
    run_controls_against_tree,
    run_step_analysis,
)
from pathfinder.services.experiment.types import (
    ControlTestResult,
    ExperimentMetrics,
)

logger = get_logger(__name__)


async def phase_evaluate(
    pctx: PhaseContext,
) -> tuple[ControlTestResult, ExperimentMetrics]:
    """Run control-test evaluation, compute metrics, and enrich gene lists.

    :returns: ``(control_result, metrics)`` for downstream phases.
    """
    config, experiment = pctx.config, pctx.experiment
    await pctx.emit("evaluating", message="Running control tests...")

    if config.target_gene_ids:
        # Gene set mode: evaluate using gene IDs directly, no WDK calls.

        result = evaluate_gene_ids_against_controls(
            gene_ids=config.target_gene_ids,
            positive_controls=config.positive_controls or [],
            negative_controls=config.negative_controls or [],
            site_id=config.site_id,
            record_type=config.record_type,
        )
    elif config.is_tree_mode and config.step_tree is not None:
        result = await run_controls_against_tree(
            ControlsContext.from_config(config),
            config.step_tree,
        )
    else:
        result = await run_single_step_controls(config, config.parameters)

    metrics = await apply_control_result(config, experiment, result)

    await pctx.emit(
        "evaluating",
        message="Evaluation complete",
        metrics=metrics.model_dump(by_alias=True),
    )
    pctx.store.save(experiment)

    return result, metrics


async def phase_step_analysis(
    pctx: PhaseContext,
    tree: StrategyStepNode,
    baseline_result: ControlTestResult,
) -> None:
    """Run step-decomposition analysis for multi-step experiments."""
    config, experiment = pctx.config, pctx.experiment

    await pctx.emit("step_analysis", message="Running step decomposition analysis...")

    async def _progress(event: JSONObject) -> None:
        data = event.get("data", {})
        msg = data.get("message", "") if isinstance(data, dict) else ""
        await pctx.emit("step_analysis", message=str(msg), stepAnalysisProgress=data)

    ctx = ControlsContext.from_config(config)
    experiment.step_analysis = await run_step_analysis(
        ctx,
        tree,
        baseline_result,
        phases=config.step_analysis_phases,
        progress_callback=_progress,
    )
    pctx.store.save(experiment)

    metrics_json = (
        experiment.metrics.model_dump(by_alias=True) if experiment.metrics else {}
    )
    await pctx.emit(
        "step_analysis", message="Step analysis complete", metrics=metrics_json
    )


async def phase_persist_strategy(
    pctx: PhaseContext,
    final_tree: StrategyStepNode | None,
) -> None:
    """Create a persisted WDK strategy for result exploration (best-effort)."""
    config, experiment = pctx.config, pctx.experiment
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
        pctx.store.save(experiment)
    except (AppError, RuntimeError) as exc:
        logger.warning(
            "Failed to persist WDK strategy for experiment",
            experiment_id=experiment.id,
            error=str(exc),
        )


async def phase_rank_metrics(
    pctx: PhaseContext,
) -> list[str]:
    """Compute rank-based metrics when a sort attribute is configured.

    :returns: Ordered result IDs (for downstream robustness phase).
    """
    config, experiment = pctx.config, pctx.experiment
    is_ranked = config.sort_attribute is not None
    if not is_ranked or experiment.wdk_step_id is None:
        return []

    try:
        await pctx.emit("evaluating", message="Computing rank-based metrics...")

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
            pctx.store.save(experiment)
    except (AppError, ZeroDivisionError) as exc:
        logger.warning(
            "Rank metrics computation failed",
            experiment_id=experiment.id,
            error=str(exc),
        )
        return []
    else:
        return ordered_ids
