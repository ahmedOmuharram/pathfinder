"""Analysis endpoints: cross-validate, enrich, re-evaluate, threshold-sweep, etc."""

from __future__ import annotations

import json
import math
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.errors import NotFoundError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    Experiment,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    AiAssistRequest,
    CustomEnrichRequest,
    EnrichmentCompareRequest,
    OverlapRequest,
    RunCrossValidationRequest,
    RunEnrichmentRequest,
    ThresholdSweepRequest,
)

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Non-parametric routes (must be defined before /{experiment_id} routes)
# ---------------------------------------------------------------------------


@router.post("/overlap")
async def compute_overlap(body: OverlapRequest) -> JSONObject:
    """Compute pairwise gene set overlap between experiments.

    For each experiment the result gene set is the union of TP and FP genes.
    Returns Jaccard similarity, shared/unique genes, and membership counts.
    """
    store = get_experiment_store()
    experiments: list[Experiment] = []
    for eid in body.experiment_ids:
        exp = await store.aget(eid)
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        experiments.append(exp)

    # Build gene sets (TP + FP) per experiment
    gene_sets: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for exp in experiments:
        genes = {g.id for g in exp.true_positive_genes} | {
            g.id for g in exp.false_positive_genes
        }
        gene_sets[exp.id] = genes
        labels[exp.id] = exp.config.name or exp.id

    # Pairwise comparisons
    ids = body.experiment_ids
    pairwise: list[JSONObject] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a_id, b_id = ids[i], ids[j]
            set_a, set_b = gene_sets[a_id], gene_sets[b_id]
            shared = set_a & set_b
            combined = set_a | set_b
            jaccard = len(shared) / len(combined) if combined else 0.0
            pairwise.append(
                {
                    "experimentA": a_id,
                    "experimentB": b_id,
                    "labelA": labels[a_id],
                    "labelB": labels[b_id],
                    "sizeA": len(set_a),
                    "sizeB": len(set_b),
                    "intersection": len(shared),
                    "union": len(combined),
                    "jaccard": round(jaccard, 4),
                    "sharedGenes": sorted(shared),
                    "uniqueA": sorted(set_a - set_b),
                    "uniqueB": sorted(set_b - set_a),
                }
            )

    # Per-experiment summary
    all_genes: set[str] = set()
    for gs in gene_sets.values():
        all_genes |= gs

    # Track which experiments each gene appears in
    gene_to_experiments: dict[str, list[str]] = {}
    for eid, gs in gene_sets.items():
        for gid in gs:
            gene_to_experiments.setdefault(gid, []).append(eid)

    # Genes present in every experiment
    universal = {
        gid for gid, exps in gene_to_experiments.items() if len(exps) == len(ids)
    }

    per_experiment: list[JSONObject] = []
    for exp in experiments:
        gs = gene_sets[exp.id]
        shared_count = sum(1 for gid in gs if len(gene_to_experiments[gid]) > 1)
        per_experiment.append(
            {
                "experimentId": exp.id,
                "label": labels[exp.id],
                "totalGenes": len(gs),
                "uniqueGenes": len(gs) - shared_count,
                "sharedGenes": shared_count,
            }
        )

    gene_membership: list[JSONObject] = [
        {
            "geneId": gid,
            "foundIn": len(exps),
            "totalExperiments": len(ids),
            "experiments": sorted(exps),
        }
        for gid, exps in sorted(gene_to_experiments.items())
    ]

    return {
        "experimentIds": list(ids),
        "experimentLabels": cast(JSONValue, labels),
        "pairwise": cast(JSONValue, pairwise),
        "perExperiment": cast(JSONValue, per_experiment),
        "universalGenes": sorted(universal),
        "totalUniqueGenes": len(all_genes),
        "geneMembership": cast(JSONValue, gene_membership),
    }


@router.post("/enrichment-compare")
async def compare_enrichment(body: EnrichmentCompareRequest) -> JSONObject:
    """Compare enrichment results across experiments.

    Builds a term-by-experiment matrix of fold-enrichment scores.
    Optionally filters to a single analysis type.
    """
    store = get_experiment_store()
    experiments: list[Experiment] = []
    for eid in body.experiment_ids:
        exp = await store.aget(eid)
        if not exp:
            raise NotFoundError(title=f"Experiment {eid} not found")
        experiments.append(exp)

    ids = body.experiment_ids
    labels: dict[str, str] = {
        exp.id: (exp.config.name or exp.id) for exp in experiments
    }

    # Collect scores: term_key -> { experiment_id -> fold_enrichment }
    # Also track term metadata (name, analysis type)
    term_scores: dict[str, dict[str, float]] = {}
    term_meta: dict[str, tuple[str, str]] = {}  # term_key -> (term_name, analysis_type)

    for exp in experiments:
        for er in exp.enrichment_results:
            if body.analysis_type and er.analysis_type != body.analysis_type:
                continue
            for term in er.terms:
                key = f"{er.analysis_type}:{term.term_id}"
                if key not in term_meta:
                    term_meta[key] = (term.term_name, er.analysis_type)
                    term_scores[key] = {}
                term_scores[key][exp.id] = term.fold_enrichment

    # Build rows sorted by max score descending
    rows: list[JSONObject] = []
    for key in sorted(
        term_scores,
        key=lambda k: max(term_scores[k].values()) if term_scores[k] else 0.0,
        reverse=True,
    ):
        name, analysis_type = term_meta[key]
        scores_map = term_scores[key]
        scores_for_row: dict[str, JSONValue] = {
            eid: round(scores_map[eid], 4) if eid in scores_map else None for eid in ids
        }
        max_score = max(scores_map.values()) if scores_map else 0.0
        rows.append(
            {
                "termKey": key,
                "termName": name,
                "analysisType": analysis_type,
                "scores": cast(JSONValue, scores_for_row),
                "maxScore": round(max_score, 4),
                "experimentCount": len(scores_map),
            }
        )

    return {
        "experimentIds": list(ids),
        "experimentLabels": cast(JSONValue, labels),
        "rows": cast(JSONValue, rows),
        "totalTerms": len(rows),
    }


@router.post(
    "/ai-assist",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of AI assistant response",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def ai_assist(request: AiAssistRequest) -> StreamingResponse:
    """AI assistant for the experiment wizard.

    Streams a response with tool-use activity (web/literature search, site
    catalog lookup, gene lookup) to help the user with the current wizard step.
    """
    from veupath_chatbot.services.experiment.assistant import run_assistant

    history_raw = request.history if isinstance(request.history, list) else []
    history: list[JSONObject] = [h for h in history_raw if isinstance(h, dict)]

    async def _generate() -> AsyncIterator[str]:
        saw_end = False
        try:
            async for event in run_assistant(
                site_id=request.site_id,
                step=request.step,
                message=request.message,
                context=request.context,
                history=history,
                model_override=request.model,
            ):
                event_type = event.get("type", "message")
                if event_type == "message_end":
                    saw_end = True
                yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
        except Exception as exc:
            logger.error("AI assist failed", error=str(exc), exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        if not saw_end:
            yield f"event: message_end\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Parametric routes (/{experiment_id}/...)
# ---------------------------------------------------------------------------


@router.post("/{experiment_id}/cross-validate")
async def run_cv(
    experiment_id: str,
    request: RunCrossValidationRequest,
) -> JSONObject:
    """Run cross-validation on an existing experiment."""
    from veupath_chatbot.services.experiment.cross_validation import (
        run_cross_validation,
        run_cross_validation_tree,
    )
    from veupath_chatbot.services.experiment.types import cv_result_to_json

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    is_tree_mode = exp.config.mode != "single" and isinstance(
        exp.config.step_tree, dict
    )

    if is_tree_mode:
        cv = await run_cross_validation_tree(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            tree=exp.config.step_tree,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            controls_value_format=exp.config.controls_value_format,
            positive_controls=exp.config.positive_controls,
            negative_controls=exp.config.negative_controls,
            k=request.k_folds,
            full_metrics=exp.metrics,
        )
    else:
        cv = await run_cross_validation(
            site_id=exp.config.site_id,
            record_type=exp.config.record_type,
            search_name=exp.config.search_name,
            parameters=exp.config.parameters,
            controls_search_name=exp.config.controls_search_name,
            controls_param_name=exp.config.controls_param_name,
            positive_controls=exp.config.positive_controls,
            negative_controls=exp.config.negative_controls,
            controls_value_format=exp.config.controls_value_format,
            k=request.k_folds,
            full_metrics=exp.metrics,
        )

    exp.cross_validation = cv
    store.save(exp)
    return cv_result_to_json(cv)


@router.post("/{experiment_id}/enrich")
async def run_enrichment(
    experiment_id: str,
    request: RunEnrichmentRequest,
) -> list[JSONObject]:
    """Run enrichment analysis on an existing experiment's results."""
    from veupath_chatbot.services.experiment.enrichment import (
        run_enrichment_analysis,
        run_enrichment_on_step,
    )
    from veupath_chatbot.services.experiment.types import enrichment_result_to_json

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    use_step = exp.config.mode != "single" and exp.wdk_step_id is not None

    results: list[JSONObject] = []
    for enrich_type in request.enrichment_types:
        try:
            if use_step:
                er = await run_enrichment_on_step(
                    site_id=exp.config.site_id,
                    step_id=exp.wdk_step_id,
                    analysis_type=enrich_type,
                )
            else:
                er = await run_enrichment_analysis(
                    site_id=exp.config.site_id,
                    record_type=exp.config.record_type,
                    search_name=exp.config.search_name,
                    parameters=exp.config.parameters,
                    analysis_type=enrich_type,
                )
            exp.enrichment_results.append(er)
            results.append(enrichment_result_to_json(er))
        except Exception as exc:
            logger.warning(
                "Enrichment analysis failed",
                analysis_type=enrich_type,
                error=str(exc),
            )

    store.save(exp)
    return results


@router.post("/{experiment_id}/re-evaluate")
async def re_evaluate_experiment(experiment_id: str) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
    from veupath_chatbot.services.experiment.types import experiment_to_json

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

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

    from veupath_chatbot.services.experiment.service import (
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
    store.save(exp)

    return experiment_to_json(exp)


@router.post("/{experiment_id}/custom-enrich")
async def custom_enrichment(
    experiment_id: str,
    request: CustomEnrichRequest,
) -> JSONObject:
    """Test enrichment of a custom gene set against the experiment results."""
    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    result_ids = {g.id for g in exp.true_positive_genes} | {
        g.id for g in exp.false_positive_genes
    }
    positive_ids = {g.id for g in exp.true_positive_genes}
    gene_set = set(request.gene_ids)
    overlap = result_ids & gene_set
    tp_in_overlap = positive_ids & gene_set

    background = (
        len(result_ids)
        + len({g.id for g in exp.false_negative_genes})
        + len({g.id for g in exp.true_negative_genes})
    )
    background = max(background, 1)
    result_size = max(len(result_ids), 1)
    gene_set_size = max(len(gene_set), 1)

    expected = result_size * gene_set_size / background
    fold = len(overlap) / expected if expected > 0 else 0.0

    a = len(overlap)  # in result AND in gene set
    b = gene_set_size - a  # in gene set but NOT in result
    c = result_size - a  # in result but NOT in gene set
    d = max(background - a - b - c, 0)  # in neither
    odds = (a * max(d, 1)) / (max(b, 1) * max(c, 1))

    n = background
    k = result_size
    m = gene_set_size
    x = len(overlap)
    log_p = _hypergeometric_log_sf(x, n, k, m)
    p_value = min(1.0, math.exp(log_p))

    return {
        "geneSetName": request.gene_set_name,
        "geneSetSize": len(gene_set),
        "overlapCount": len(overlap),
        "overlapGenes": cast(JSONValue, sorted(overlap)),
        "backgroundSize": background,
        "tpCount": len(tp_in_overlap),
        "foldEnrichment": round(fold, 4),
        "pValue": p_value,
        "oddsRatio": round(odds, 4),
    }


@router.post("/{experiment_id}/threshold-sweep")
async def threshold_sweep(
    experiment_id: str,
    request: ThresholdSweepRequest,
) -> JSONObject:
    """Sweep a numeric parameter across a range and compute metrics at each point."""
    from veupath_chatbot.services.experiment.metrics import metrics_from_control_result

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

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
    experiment_id: str,
    body: dict[str, object],
) -> JSONObject:
    """Analyse per-step contribution to overall result for multi-step experiments.

    Evaluates controls against each leaf step individually to show how much
    each step contributes to the final strategy result.
    """
    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

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
async def get_experiment_report(experiment_id: str) -> StreamingResponse:
    """Generate and return a self-contained HTML report for an experiment."""
    from veupath_chatbot.services.experiment.report import generate_experiment_report

    store = get_experiment_store()
    exp = await store.aget(experiment_id)
    if not exp:
        raise NotFoundError(title="Experiment not found")

    html_content = generate_experiment_report(exp)

    return StreamingResponse(
        iter([html_content]),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="experiment-{experiment_id}-report.html"',
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hypergeometric_log_sf(x: int, n: int, k: int, m: int) -> float:
    """Approximate log survival function for hypergeometric distribution.

    Uses a normal approximation of P(X >= x) for speed.  Returns 0.0
    (i.e. p=1.0) when the observed count is at or below the mean.
    """
    mean = k * m / n
    var = k * m * (n - k) * (n - m) / (n * n * max(n - 1, 1))
    std = max(math.sqrt(var), 1e-12)
    z = (x - mean) / std
    if z <= 0:
        return 0.0  # no enrichment → p = 1.0
    # Upper-tail approximation: log(1 - Φ(z)) ≈ -log(z) - 0.5*z² - 0.5*log(2π)
    # for z >> 1.  For moderate z, use math.erfc.
    log_sf = math.log(max(math.erfc(z / math.sqrt(2)) / 2, 1e-300))
    return log_sf
