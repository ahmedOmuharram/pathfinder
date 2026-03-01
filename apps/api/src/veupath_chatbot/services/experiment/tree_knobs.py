"""Multi-step tree-knob optimization.

Tunes threshold parameters and boolean operators across a strategy tree
using Optuna, optimizing for rank-based objectives (Precision@K,
Enrichment@K) with optional list-size constraints.
"""

from __future__ import annotations

import copy
import math
import time

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OperatorKnob,
    ThresholdKnob,
    TreeOptimizationResult,
    TreeOptimizationTrial,
)

logger = get_logger(__name__)


def _safe_int(val: JSONValue, default: int = 0) -> int:
    """Safely convert a JSONValue to int."""
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            return default
    return default


async def optimize_tree_knobs(
    *,
    site_id: str,
    record_type: str,
    base_tree: JSONObject,
    threshold_knobs: list[ThresholdKnob],
    operator_knobs: list[OperatorKnob],
    positive_controls: list[str],
    negative_controls: list[str],
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    objective: str = "precision_at_50",
    budget: int = 50,
    max_list_size: int | None = None,
    progress_callback: object | None = None,
) -> TreeOptimizationResult:
    """Run Optuna optimization over tree knobs.

    :param base_tree: ``PlanStepNode``-shaped dict (the template tree).
    :param threshold_knobs: Numeric parameter knobs on leaf steps.
    :param operator_knobs: Boolean operator knobs on combine nodes.
    :param objective: Target metric name (e.g. ``precision_at_50``).
    :param budget: Maximum number of Optuna trials.
    :param max_list_size: Optional upper bound on result list size.
    :returns: Optimization result with best trial and history.
    """
    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.error("Optuna not installed — tree optimization unavailable")
        return TreeOptimizationResult(objective=objective)

    from veupath_chatbot.services.experiment.step_analysis import (
        run_controls_against_tree,
    )

    start = time.monotonic()
    all_trials: list[TreeOptimizationTrial] = []
    best_trial: TreeOptimizationTrial | None = None

    def _apply_knobs(
        tree: JSONObject,
        threshold_vals: dict[str, float],
        operator_vals: dict[str, str],
    ) -> JSONObject:
        """Return a copy of the tree with knob values applied."""
        modified = copy.deepcopy(tree)
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

        result = await run_controls_against_tree(
            site_id=site_id,
            record_type=record_type,
            tree=modified_tree,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_value_format=controls_value_format,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )

        target = result.get("target", {})
        total_results = (
            _safe_int(target.get("resultCount", 0)) if isinstance(target, dict) else 0
        )

        if max_list_size is not None and total_results > max_list_size:
            return -1.0

        pos = result.get("positive", {})
        neg = result.get("negative", {})
        pos_hits = (
            _safe_int(pos.get("intersectionCount", 0)) if isinstance(pos, dict) else 0
        )
        neg_hits = (
            _safe_int(neg.get("intersectionCount", 0)) if isinstance(neg, dict) else 0
        )
        total_pos = len(positive_controls)
        total_neg = len(negative_controls)

        tp = pos_hits
        fn = total_pos - tp
        fp = neg_hits
        tn = total_neg - fp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        random_prec = total_pos / total_results if total_results > 0 else 0.0
        enrichment = precision / random_prec if random_prec > 0 else 0.0

        score = _select_metric(
            objective,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=precision,
            recall=recall,
            specificity=specificity,
            enrichment=enrichment,
        )

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

    for _i in range(budget):
        trial = study.ask()
        score = await _objective(trial)
        study.tell(trial, score)

    elapsed = time.monotonic() - start
    return TreeOptimizationResult(
        best_trial=best_trial,
        all_trials=all_trials,
        total_time_seconds=elapsed,
        objective=objective,
    )


def _apply_knobs_recursive(
    node: JSONObject,
    threshold_vals: dict[str, float],
    operator_vals: dict[str, str],
) -> None:
    """Recursively apply knob values to a tree in-place."""
    node_id = str(node.get("id", ""))

    if node_id in operator_vals:
        node["operator"] = operator_vals[node_id]

    raw_params = node.get("parameters")
    if isinstance(raw_params, dict):
        for key, val in threshold_vals.items():
            step_id, param_name = key.split(":", 1)
            if node_id == step_id:
                raw_params[param_name] = str(val)

    primary = node.get("primaryInput")
    if isinstance(primary, dict):
        _apply_knobs_recursive(primary, threshold_vals, operator_vals)
    secondary = node.get("secondaryInput")
    if isinstance(secondary, dict):
        _apply_knobs_recursive(secondary, threshold_vals, operator_vals)


def _extract_k(objective: str) -> int:
    """Extract K from objective name like 'precision_at_50'."""
    parts = objective.rsplit("_", 1)
    try:
        return int(parts[-1])
    except ValueError:
        return 50


def _select_metric(
    objective: str,
    *,
    tp: int,
    fp: int,
    fn: int,
    tn: int,
    precision: float,
    recall: float,
    specificity: float,
    enrichment: float,
) -> float:
    """Select the metric value based on the objective name.

    Supports: ``precision_at_K``, ``recall_at_K``, ``enrichment_at_K``,
    ``f1``, ``mcc``, ``sensitivity``, ``specificity``, ``balanced_accuracy``.
    """
    obj = objective.lower()

    if "precision" in obj:
        return precision
    if obj in ("sensitivity", "recall") or obj.startswith("recall"):
        return recall
    if "enrichment" in obj:
        return enrichment
    if "specificity" in obj:
        return specificity
    if "balanced_accuracy" in obj:
        return (recall + specificity) / 2
    if "mcc" in obj:
        denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        return ((tp * tn - fp * fn) / denom) if denom > 0 else 0.0
    if "f1" in obj:
        denom = precision + recall
        return (2 * precision * recall / denom) if denom > 0 else 0.0

    return precision
