"""Control evaluation logic: run trees/steps against control sets and extract metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import resolve_controls_param_type
from veupath_chatbot.services.experiment.types import ControlValueFormat

logger = get_logger(__name__)


async def run_controls_against_tree(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> JSONObject:
    """Materialise a ``PlanStepNode`` tree, intersect with controls, return metrics.

    Creates a temporary WDK strategy containing the full tree, adds an
    intersection step with each control set on top of the root, queries the
    result counts, then deletes everything.

    Returns the same shape as :func:`run_positive_negative_controls` so
    :func:`metrics_from_control_result` can consume it directly.
    """
    from veupath_chatbot.services.experiment.materialization import (
        _coerce_step_id,
        _materialize_step_tree,
    )

    api = get_strategy_api(site_id)

    pos = [s.strip() for s in (positive_controls or []) if s.strip()]
    neg = [s.strip() for s in (negative_controls or []) if s.strip()]

    result: JSONObject = {
        "siteId": site_id,
        "recordType": record_type,
        "target": {"searchName": "__tree__", "resultCount": None},
        "positive": None,
        "negative": None,
    }

    async def _eval_control_set(
        control_ids: list[str],
        label: str,
    ) -> JSONObject:
        """Materialise the tree, intersect with one control set, clean up."""
        root_tree = await _materialize_step_tree(api, tree, record_type)

        param_type = await resolve_controls_param_type(
            api,
            record_type,
            controls_search_name,
            controls_param_name,
        )

        controls_params: JSONObject = {}
        if param_type == "input-dataset":
            dataset_id = await api.create_dataset(control_ids)
            controls_params[controls_param_name] = str(dataset_id)
        else:
            controls_params[controls_param_name] = "\n".join(control_ids)

        controls_step = await api.create_step(
            record_type=record_type,
            search_name=controls_search_name,
            parameters=controls_params,
            custom_name=f"Controls ({label})",
        )
        controls_step_id = _coerce_step_id(controls_step)

        combined = await api.create_combined_step(
            primary_step_id=root_tree.step_id,
            secondary_step_id=controls_step_id,
            boolean_operator="INTERSECT",
            record_type=record_type,
            custom_name=f"Tree \u2229 {label}",
        )
        combined_step_id = _coerce_step_id(combined)

        full_tree = StepTreeNode(
            combined_step_id,
            primary_input=root_tree,
            secondary_input=StepTreeNode(controls_step_id),
        )
        created = await api.create_strategy(
            step_tree=full_tree,
            name="Pathfinder tree eval",
            is_internal=True,
        )
        strategy_id: int | None = None
        if isinstance(created, dict):
            raw = created.get("id")
            if isinstance(raw, int):
                strategy_id = raw

        try:
            target_total = await api.get_step_count(root_tree.step_id)
            intersection_total = await api.get_step_count(combined_step_id)

            intersection_ids: list[str] = []
            if len(control_ids) <= 500:
                answer = await api.get_step_answer(
                    combined_step_id,
                    pagination={"offset": 0, "numRecords": min(len(control_ids), 500)},
                )
                if isinstance(answer, dict):
                    records = answer.get("records")
                    if isinstance(records, list):
                        for rec in records:
                            if not isinstance(rec, dict):
                                continue
                            pk = rec.get("id")
                            if isinstance(pk, list) and pk:
                                first = pk[0]
                                if isinstance(first, dict):
                                    intersection_ids.append(str(first.get("value", "")))

            return {
                "controlsCount": len(control_ids),
                "intersectionCount": intersection_total,
                "intersectionIds": list(intersection_ids),
                "intersectionIdsSample": list(intersection_ids[:50]),
                "targetStepId": root_tree.step_id,
                "targetResultCount": target_total,
            }
        finally:
            if strategy_id is not None:
                import contextlib

                with contextlib.suppress(Exception):
                    await api.delete_strategy(strategy_id)

    if pos:
        pos_payload = await _eval_control_set(pos, "positive")
        raw_count = pos_payload.get("intersectionCount")
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
        intersection_ids_val = pos_payload.get("intersectionIds")
        found = (
            set(intersection_ids_val)
            if isinstance(intersection_ids_val, list)
            else set()
        )
        missing = [x for x in pos if found and x not in found]

        result["target"] = {
            "searchName": "__tree__",
            "resultCount": pos_payload.get("targetResultCount"),
        }
        result["positive"] = {
            **pos_payload,
            "missingIdsSample": list(missing[:50]),
            "recall": count / len(pos) if pos else None,
        }

    if neg:
        neg_payload = await _eval_control_set(neg, "negative")
        raw_count = neg_payload.get("intersectionCount")
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
        intersection_ids_val = neg_payload.get("intersectionIds")
        hit_ids = (
            set(intersection_ids_val)
            if isinstance(intersection_ids_val, list)
            else set()
        )

        if result["target"] is None or (
            isinstance(result["target"], dict)
            and result["target"].get("resultCount") is None
        ):
            result["target"] = {
                "searchName": "__tree__",
                "resultCount": neg_payload.get("targetResultCount"),
            }
        result["negative"] = {
            **neg_payload,
            "unexpectedHitsSample": list(list(hit_ids)[:50]),
            "falsePositiveRate": count / len(neg) if neg else None,
        }

    return result


async def _evaluate_tree_against_controls(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
) -> JSONObject:
    """Internal alias for :func:`run_controls_against_tree`."""
    return await run_controls_against_tree(
        site_id=site_id,
        record_type=record_type,
        tree=tree,
        controls_search_name=controls_search_name,
        controls_param_name=controls_param_name,
        controls_value_format=controls_value_format,
        positive_controls=positive_controls or None,
        negative_controls=negative_controls or None,
    )


async def _evaluate_single_step(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
) -> JSONObject:
    """Evaluate a single leaf search against controls."""
    from veupath_chatbot.services.control_tests import (
        run_positive_negative_controls,
    )

    return await run_positive_negative_controls(
        site_id=site_id,
        record_type=record_type,
        target_search_name=search_name,
        target_parameters=parameters,
        controls_search_name=controls_search_name,
        controls_param_name=controls_param_name,
        positive_controls=positive_controls or None,
        negative_controls=negative_controls or None,
        controls_value_format=controls_value_format,
    )


@dataclass
class _EvalCounts:
    """Structured result from extracting control-test counts."""

    pos_hits: int = 0
    pos_total: int = 0
    neg_hits: int = 0
    neg_total: int = 0
    total_results: int = 0
    pos_ids: list[str] = field(default_factory=list)
    neg_ids: list[str] = field(default_factory=list)


def _extract_eval_counts(result: JSONObject) -> _EvalCounts:
    """Pull hit counts and IDs from a control-test result."""
    pos = result.get("positive") or {}
    neg = result.get("negative") or {}
    tgt = result.get("target") or {}

    pos_data = pos if isinstance(pos, dict) else {}
    neg_data = neg if isinstance(neg, dict) else {}
    tgt_data = tgt if isinstance(tgt, dict) else {}

    def _int(v: object) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        return 0

    def _str_list(v: object) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    return _EvalCounts(
        pos_hits=_int(pos_data.get("intersectionCount")),
        pos_total=_int(pos_data.get("controlsCount")),
        neg_hits=_int(neg_data.get("intersectionCount")),
        neg_total=_int(neg_data.get("controlsCount")),
        total_results=_int(tgt_data.get("resultCount")),
        pos_ids=_str_list(pos_data.get("intersectionIds")),
        neg_ids=_str_list(neg_data.get("intersectionIds")),
    )


def _f1(recall: float, fpr: float, neg_total: int) -> float:
    """Approximate F1 from recall and FPR."""
    specificity = 1.0 - fpr if neg_total > 0 else 1.0
    precision = specificity  # proxy when we lack total result count
    denom = precision + recall
    if denom == 0:
        return 0.0
    return 2 * precision * recall / denom
