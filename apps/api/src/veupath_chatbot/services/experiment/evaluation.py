"""Evaluation service: re-evaluate and threshold sweep.

Pure business logic extracted from the transport handler. No HTTP/SSE
concerns here -- callers (routers, tools, etc.) wrap the results in
whatever transport format they need.
"""

import asyncio
import json as json_mod
from collections.abc import AsyncIterator

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.helpers import extract_and_enrich_genes
from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentMetrics,
    experiment_to_json,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SWEEP_CONCURRENCY = 3
"""Max parallel WDK control-test runs per sweep."""

SWEEP_TIMEOUT_S = 4 * 60
"""Server-side timeout for the entire sweep."""

SWEEP_POINT_TIMEOUT_S = 90
"""Per-point timeout; prevents one slow point from blocking all."""

# ---------------------------------------------------------------------------
# Re-evaluate
# ---------------------------------------------------------------------------


async def re_evaluate(exp: Experiment) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy.

    Updates the experiment in-place (metrics + gene lists) and persists it.
    Returns the full experiment JSON.
    """
    if exp.config.is_tree_mode:
        from veupath_chatbot.services.experiment.step_analysis import (
            run_controls_against_tree,
        )

        step_tree = exp.config.step_tree
        if not isinstance(step_tree, dict):
            raise ValueError("step_tree must be a dict in tree mode")

        result = await run_controls_against_tree(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            tree=step_tree,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            controls_value_format=exp.config.controls_value_format,
            positive_controls=exp.config.positive_controls or None,
            negative_controls=exp.config.negative_controls or None,
        )
    else:
        result = await run_positive_negative_controls(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            target_search_name=exp.config.search_name,
            target_parameters=exp.config.parameters,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            positive_controls=exp.config.positive_controls or None,
            negative_controls=exp.config.negative_controls or None,
            controls_value_format=exp.config.controls_value_format,
        )

    metrics = metrics_from_control_result(result)
    exp.metrics = metrics
    (
        exp.true_positive_genes,
        exp.false_negative_genes,
        exp.false_positive_genes,
        exp.true_negative_genes,
    ) = await extract_and_enrich_genes(
        site_id=exp.config.site_id,
        result=result,
        negative_controls=exp.config.negative_controls,
    )
    get_experiment_store().save(exp)

    return experiment_to_json(exp)


# ---------------------------------------------------------------------------
# Threshold sweep helpers
# ---------------------------------------------------------------------------


def compute_sweep_values(
    *,
    sweep_type: str,
    values: list[str] | None,
    min_value: float | None,
    max_value: float | None,
    steps: int,
) -> list[str]:
    """Compute the list of parameter values for a sweep.

    :param sweep_type: ``"numeric"`` or ``"categorical"``.
    :param values: Explicit values for categorical sweeps.
    :param min_value: Range start for numeric sweeps.
    :param max_value: Range end for numeric sweeps.
    :param steps: Number of evenly-spaced points for numeric sweeps.
    :returns: List of stringified sweep values.
    :raises ValidationError: On invalid inputs.
    """
    if sweep_type == "categorical":
        if not values or len(values) == 0:
            raise ValidationError(
                title="Missing values",
                detail="Categorical sweep requires a non-empty 'values' list.",
            )
        return values

    if min_value is None or max_value is None:
        raise ValidationError(
            title="Missing range",
            detail="Numeric sweep requires 'minValue' and 'maxValue'.",
        )
    step_size = (max_value - min_value) / max(steps - 1, 1)
    return [str(min_value + i * step_size) for i in range(steps)]


def validate_sweep_parameter(exp: Experiment, param_name: str) -> None:
    """Ensure *param_name* exists in the experiment config.

    :raises ValidationError: If the parameter is missing.
    """
    if param_name not in exp.config.parameters:
        raise ValidationError(
            title="Parameter not found",
            detail=f"Parameter '{param_name}' is not in this experiment's config.",
        )


def format_metrics_dict(m: ExperimentMetrics) -> JSONObject:
    """Format an :class:`ExperimentMetrics` into a JSON-friendly dict."""
    return {
        "sensitivity": round(m.sensitivity, 4),
        "specificity": round(m.specificity, 4),
        "precision": round(m.precision, 4),
        "f1Score": round(m.f1_score, 4),
        "mcc": round(m.mcc, 4),
        "balancedAccuracy": round(m.balanced_accuracy, 4),
        "totalResults": m.total_results,
        "falsePositiveRate": round(m.false_positive_rate, 4),
    }


async def run_sweep_point(
    *,
    exp: Experiment,
    param_name: str,
    value: str,
    is_categorical: bool,
) -> JSONObject:
    """Run a single sweep point: modify the parameter and evaluate.

    :returns: Dict with ``value``, ``metrics`` (or ``None``), and optionally ``error``.
    """
    modified_params = dict(exp.config.parameters)
    modified_params[param_name] = value

    try:
        response_value: float | str = float(value) if not is_categorical else value
    except ValueError:
        response_value = value

    try:
        result = await asyncio.wait_for(
            run_positive_negative_controls(
                site_id=exp.config.site_id,
                record_type=exp.config.record_type,
                target_search_name=exp.config.search_name,
                target_parameters=modified_params,
                controls_search_name=exp.config.controls_search_name,
                controls_param_name=exp.config.controls_param_name,
                positive_controls=exp.config.positive_controls or None,
                negative_controls=exp.config.negative_controls or None,
                controls_value_format=exp.config.controls_value_format,
                skip_cleanup=True,
            ),
            timeout=SWEEP_POINT_TIMEOUT_S,
        )
        m = metrics_from_control_result(result)
        return {"value": response_value, "metrics": format_metrics_dict(m)}
    except Exception as exc:
        logger.warning(
            "Threshold sweep point failed",
            param=param_name,
            value=value,
            error=str(exc),
        )
        return {"value": response_value, "metrics": None, "error": str(exc)}


async def cleanup_before_sweep(site_id: str) -> None:
    """Best-effort cleanup of leaked internal control-test strategies."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
    from veupath_chatbot.services.control_helpers import (
        cleanup_internal_control_test_strategies,
    )

    try:
        api = get_strategy_api(site_id)
        strategies = await api.list_strategies()
        await cleanup_internal_control_test_strategies(api, strategies)
    except Exception as exc:
        logger.warning(
            "Pre-sweep cleanup of leaked control-test strategies failed",
            site_id=site_id,
            error=str(exc),
        )


async def generate_sweep_events(
    *,
    exp: Experiment,
    param_name: str,
    sweep_type: str,
    sweep_values: list[str],
) -> AsyncIterator[str]:
    """Run the full sweep and yield SSE-formatted events.

    Yields ``sweep_point`` events as each point completes, then a final
    ``sweep_complete`` event with all sorted results.
    """
    is_categorical = sweep_type == "categorical"
    total_points = len(sweep_values)

    await cleanup_before_sweep(exp.config.site_id)

    semaphore = asyncio.Semaphore(SWEEP_CONCURRENCY)
    completed_count = 0
    all_points: list[JSONObject] = []

    async def _bounded_point(val: str) -> JSONObject:
        async with semaphore:
            return await run_sweep_point(
                exp=exp,
                param_name=param_name,
                value=val,
                is_categorical=is_categorical,
            )

    tasks = {asyncio.ensure_future(_bounded_point(v)): v for v in sweep_values}

    try:
        async with asyncio.timeout(SWEEP_TIMEOUT_S):
            for coro in asyncio.as_completed(tasks):
                point = await coro
                completed_count += 1
                all_points.append(point)
                event_data = json_mod.dumps(
                    {
                        "point": point,
                        "completedCount": completed_count,
                        "totalCount": total_points,
                    }
                )
                yield f"event: sweep_point\ndata: {event_data}\n\n"

    except TimeoutError:
        logger.warning(
            "Threshold sweep timed out",
            param=param_name,
            completed=completed_count,
            total=total_points,
        )
        for task in tasks:
            task.cancel()

    # Sort: numeric by value, categorical by original order.
    if is_categorical:
        order = {v: i for i, v in enumerate(sweep_values)}
        all_points.sort(key=lambda p: order.get(str(p.get("value", "")), 0))
    else:

        def _numeric_value(p: JSONObject) -> float:
            v = p.get("value", 0)
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                return float(v)
            return 0.0

        all_points.sort(key=_numeric_value)

    final_data = json_mod.dumps(
        {
            "parameter": param_name,
            "sweepType": sweep_type,
            "points": all_points,
        }
    )
    yield f"event: sweep_complete\ndata: {final_data}\n\n"
