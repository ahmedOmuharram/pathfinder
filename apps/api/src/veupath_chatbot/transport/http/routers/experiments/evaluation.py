"""Evaluation endpoints: re-evaluate, threshold-sweep, step-contributions, report."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import ControlValueFormat
from veupath_chatbot.transport.http.deps import ExperimentDep
from veupath_chatbot.transport.http.schemas.experiments import ThresholdSweepRequest

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{experiment_id}/re-evaluate")
async def re_evaluate_experiment(exp: ExperimentDep) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
    from veupath_chatbot.services.experiment.types import experiment_to_json

    is_tree_mode = exp.config.mode != "single" and isinstance(
        exp.config.step_tree, dict
    )

    if is_tree_mode:
        from veupath_chatbot.services.experiment.step_analysis import (
            run_controls_against_tree,
        )

        result = await run_controls_against_tree(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            tree=exp.config.step_tree,
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

    from veupath_chatbot.services.experiment.helpers import (
        _extract_gene_list,
        _extract_id_set,
    )

    metrics = metrics_from_control_result(result)
    exp.metrics = metrics
    exp.true_positive_genes = _extract_gene_list(result, "positive", "intersectionIds")
    exp.false_negative_genes = _extract_gene_list(
        result, "positive", "missingIdsSample"
    )
    exp.false_positive_genes = _extract_gene_list(result, "negative", "intersectionIds")
    exp.true_negative_genes = _extract_gene_list(
        result,
        "negative",
        "missingIdsSample",
        fallback_from_controls=True,
        all_controls=exp.config.negative_controls,
        hit_ids=_extract_id_set(result, "negative", "intersectionIds"),
    )
    get_experiment_store().save(exp)

    return experiment_to_json(exp)


@router.post("/{experiment_id}/threshold-sweep")
async def threshold_sweep(
    exp: ExperimentDep,
    request: ThresholdSweepRequest,
) -> JSONObject:
    """Sweep a numeric parameter across a range and compute metrics at each point."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result

    param_name = request.parameter_name
    if param_name not in exp.config.parameters:
        raise NotFoundError(
            title="Parameter not found",
            detail=f"Parameter '{param_name}' is not in this experiment's config.",
        )

    step_size = (request.max_value - request.min_value) / max(request.steps - 1, 1)
    values = [request.min_value + i * step_size for i in range(request.steps)]

    points: list[JSONObject] = []
    for val in values:
        modified_params = dict(exp.config.parameters)
        modified_params[param_name] = str(val)

        try:
            result = await run_positive_negative_controls(
                site_id=exp.config.site_id,
                record_type=exp.config.record_type,
                target_search_name=exp.config.search_name,
                target_parameters=modified_params,
                controls_search_name=exp.config.controls_search_name,
                controls_param_name=exp.config.controls_param_name,
                positive_controls=exp.config.positive_controls or None,
                negative_controls=exp.config.negative_controls or None,
                controls_value_format=exp.config.controls_value_format,
            )
            m = metrics_from_control_result(result)
            points.append(
                {
                    "value": val,
                    "metrics": {
                        "sensitivity": round(m.sensitivity, 4),
                        "specificity": round(m.specificity, 4),
                        "precision": round(m.precision, 4),
                        "f1Score": round(m.f1_score, 4),
                        "mcc": round(m.mcc, 4),
                        "balancedAccuracy": round(m.balanced_accuracy, 4),
                        "totalResults": m.total_results,
                        "falsePositiveRate": round(m.false_positive_rate, 4),
                    },
                }
            )
        except Exception as exc:
            logger.warning(
                "Threshold sweep point failed",
                param=param_name,
                value=val,
                error=str(exc),
            )
            points.append({"value": val, "metrics": None, "error": str(exc)})

    return {"parameter": param_name, "points": cast(JSONValue, points)}


@router.post("/{experiment_id}/step-contributions")
async def step_contributions(
    exp: ExperimentDep,
    body: dict[str, object],
) -> JSONObject:
    """Analyse per-step contribution to overall result for multi-step experiments.

    Evaluates controls against each leaf step individually to show how much
    each step contributes to the final strategy result.
    """
    step_tree_raw = body.get("stepTree")
    if not step_tree_raw or not isinstance(step_tree_raw, dict):
        return {"contributions": []}

    def _extract_leaves(node: dict[str, object]) -> list[dict[str, object]]:
        leaves: list[dict[str, object]] = []
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if isinstance(pi, dict):
            leaves.extend(_extract_leaves(pi))
        if isinstance(si, dict):
            leaves.extend(_extract_leaves(si))
        if not isinstance(pi, dict) and not isinstance(si, dict):
            leaves.append(node)
        return leaves

    leaves = _extract_leaves(step_tree_raw)
    contributions: list[JSONObject] = []

    _valid_formats: set[ControlValueFormat] = {"newline", "json_list", "comma"}
    cvf = exp.config.controls_value_format
    controls_format: ControlValueFormat = cvf if cvf in _valid_formats else "newline"

    for leaf in leaves:
        search_name = leaf.get("searchName")
        if not isinstance(search_name, str) or not search_name:
            continue
        params = leaf.get("parameters")
        if not isinstance(params, dict):
            params = {}
        display_name = leaf.get("displayName") or search_name

        try:
            result = await run_positive_negative_controls(
                site_id=exp.config.site_id,
                record_type=exp.config.record_type,
                target_search_name=search_name,
                target_parameters=params,
                controls_search_name=exp.config.controls_search_name,
                controls_param_name=exp.config.controls_param_name,
                positive_controls=exp.config.positive_controls or None,
                negative_controls=exp.config.negative_controls or None,
                controls_value_format=controls_format,
            )
            target_data = result.get("target") or {}
            target_dict = target_data if isinstance(target_data, dict) else {}
            raw_count = target_dict.get("resultCount")
            total = int(raw_count) if isinstance(raw_count, (int, float)) else 0

            pos_data = result.get("positive") or {}
            pos_dict = pos_data if isinstance(pos_data, dict) else {}
            raw_pos_hits = pos_dict.get("intersectionCount")
            pos_hits = (
                int(raw_pos_hits) if isinstance(raw_pos_hits, (int, float)) else 0
            )

            neg_data = result.get("negative") or {}
            neg_dict = neg_data if isinstance(neg_data, dict) else {}
            raw_neg_hits = neg_dict.get("intersectionCount")
            neg_hits = (
                int(raw_neg_hits) if isinstance(raw_neg_hits, (int, float)) else 0
            )

            total_pos = (
                len(exp.config.positive_controls) if exp.config.positive_controls else 0
            )
            total_neg = (
                len(exp.config.negative_controls) if exp.config.negative_controls else 0
            )
            contributions.append(
                {
                    "stepName": str(display_name),
                    "stepSearchName": search_name,
                    "totalResults": total,
                    "positiveControlHits": pos_hits,
                    "negativeControlHits": neg_hits,
                    "positiveRecall": round(pos_hits / max(total_pos, 1), 4),
                    "negativeRecall": round(neg_hits / max(total_neg, 1), 4),
                }
            )
        except Exception as exc:
            logger.warning(
                "Step contribution analysis failed",
                step=search_name,
                error=str(exc),
            )
            contributions.append(
                {
                    "stepName": str(display_name),
                    "stepSearchName": search_name,
                    "totalResults": 0,
                    "positiveControlHits": 0,
                    "negativeControlHits": 0,
                    "positiveRecall": 0,
                    "negativeRecall": 0,
                }
            )

    return {"contributions": cast(JSONValue, contributions)}


@router.get("/{experiment_id}/report")
async def get_experiment_report(exp: ExperimentDep) -> StreamingResponse:
    """Generate and return a self-contained HTML report for an experiment."""
    from veupath_chatbot.services.experiment.report import generate_experiment_report

    html_content = generate_experiment_report(exp)

    return StreamingResponse(
        iter([html_content]),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="experiment-{exp.id}-report.html"',
        },
    )
