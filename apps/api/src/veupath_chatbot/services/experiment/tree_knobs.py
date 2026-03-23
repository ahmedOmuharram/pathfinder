"""Multi-step tree-knob optimization.

Tunes threshold parameters and boolean operators across a strategy tree
using Optuna, optimizing for rank-based objectives (Precision@K,
Enrichment@K) with optional list-size constraints.
"""

import time
from dataclasses import dataclass

import optuna

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.tree import walk_plan_tree
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.helpers import ControlsContext
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
)
from veupath_chatbot.services.experiment.step_analysis import (
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.types import (
    ExperimentMetrics,
    OperatorKnob,
    ThresholdKnob,
    TreeOptimizationResult,
    TreeOptimizationTrial,
)

logger = get_logger(__name__)


@dataclass
class TreeOptimizationOptions:
    """Options for :func:`optimize_tree_knobs`.

    Groups the optional tuning parameters so the function signature stays
    within the 6-argument limit.
    """

    objective: str = "precision_at_50"
    budget: int = 50
    max_list_size: int | None = None


async def optimize_tree_knobs(
    ctx: ControlsContext,
    base_tree: PlanStepNode,
    threshold_knobs: list[ThresholdKnob],
    operator_knobs: list[OperatorKnob],
    options: TreeOptimizationOptions | None = None,
) -> TreeOptimizationResult:
    """Run Optuna optimization over tree knobs.

    :param ctx: Controls context (site, record type, controls).
    :param base_tree: Strategy plan tree (the template tree).
    :param threshold_knobs: Numeric parameter knobs on leaf steps.
    :param operator_knobs: Boolean operator knobs on combine nodes.
    :param options: Optimization options (objective, budget, max_list_size).
    :returns: Optimization result with best trial and history.
    """
    opts = options or TreeOptimizationOptions()
    try:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.exception("Optuna not installed — tree optimization unavailable")
        return TreeOptimizationResult(objective=opts.objective)

    start = time.monotonic()
    all_trials: list[TreeOptimizationTrial] = []
    best_trial: TreeOptimizationTrial | None = None

    def _apply_knobs(
        tree: PlanStepNode,
        threshold_vals: dict[str, float],
        operator_vals: dict[str, str],
    ) -> PlanStepNode:
        """Return a copy of the tree with knob values applied."""
        modified = tree.model_copy(deep=True)
        _apply_knobs_recursive(modified, threshold_vals, operator_vals)
        return modified

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    async def _objective(trial: optuna.Trial) -> float:
        nonlocal best_trial

        threshold_vals: dict[str, float] = {}
        for knob in threshold_knobs:
            key = f"{knob.step_id}:{knob.param_name}"
            val = trial.suggest_float(
                key,
                knob.min_val,
                knob.max_val,
                step=knob.step_size or None,
            )
            threshold_vals[key] = val

        operator_vals: dict[str, str] = {}
        for op_knob in operator_knobs:
            op_val = trial.suggest_categorical(
                op_knob.combine_node_id,
                op_knob.options,
            )
            operator_vals[op_knob.combine_node_id] = str(op_val)

        modified_tree = _apply_knobs(base_tree, threshold_vals, operator_vals)

        result = await run_controls_against_tree(ctx, modified_tree)

        total_results = result.target.estimated_size or 0

        if opts.max_list_size is not None and total_results > opts.max_list_size:
            return -1.0

        pos_hits = result.positive.intersection_count if result.positive else 0
        neg_hits = result.negative.intersection_count if result.negative else 0
        total_pos = len(ctx.positive_controls)
        total_neg = len(ctx.negative_controls)

        cm = compute_confusion_matrix(
            positive_hits=pos_hits,
            total_positives=total_pos,
            negative_hits=neg_hits,
            total_negatives=total_neg,
        )
        m = compute_metrics(cm, total_results=total_results)

        random_prec = total_pos / total_results if total_results > 0 else 0.0
        enrichment = m.precision / random_prec if random_prec > 0 else 0.0

        score = _select_metric(opts.objective, metrics=m, enrichment=enrichment)

        params: dict[str, float | str] = {**threshold_vals, **operator_vals}
        t = TreeOptimizationTrial(
            trial_number=trial.number + 1,
            parameters=params,
            score=score,
            list_size=total_results,
        )
        all_trials.append(t)
        if best_trial is None or score > best_trial.score:
            best_trial = t

        return score

    for _i in range(opts.budget):
        trial = study.ask()
        score = await _objective(trial)
        study.tell(trial, score)

    elapsed = time.monotonic() - start
    return TreeOptimizationResult(
        best_trial=best_trial,
        all_trials=all_trials,
        total_time_seconds=elapsed,
        objective=opts.objective,
    )


def _apply_knobs_recursive(
    node: PlanStepNode,
    threshold_vals: dict[str, float],
    operator_vals: dict[str, str],
) -> None:
    """Recursively apply knob values to a tree in-place."""
    def _apply(n: PlanStepNode) -> None:
        nid = n.id
        if nid in operator_vals:
            n.operator = CombineOp(operator_vals[nid])
        for key, val in threshold_vals.items():
            step_id, param_name = key.split(":", 1)
            if nid == step_id:
                n.parameters[param_name] = str(val)

    walk_plan_tree(node, _apply)


def _select_metric(
    objective: str,
    *,
    metrics: ExperimentMetrics,
    enrichment: float,
) -> float:
    """Select the metric value based on the objective name.

    Supports: ``precision_at_K``, ``recall_at_K``, ``enrichment_at_K``,
    ``f1``, ``mcc``, ``sensitivity``, ``specificity``, ``balanced_accuracy``.
    """
    obj = objective.lower()

    lookup: dict[str, float] = {
        "precision": metrics.precision,
        "recall": metrics.sensitivity,
        "sensitivity": metrics.sensitivity,
        "enrichment": enrichment,
        "specificity": metrics.specificity,
        "balanced_accuracy": metrics.balanced_accuracy,
        "mcc": metrics.mcc,
        "f1": metrics.f1_score,
    }
    for keyword, value in lookup.items():
        if keyword in obj:
            return value

    return metrics.precision
