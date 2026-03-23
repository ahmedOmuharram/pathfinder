"""Control evaluation logic: run trees/steps against control sets and extract metrics."""

from dataclasses import dataclass, field

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKSearchConfig,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.control_tests import (
    _extract_intersection_data,
    resolve_controls_param_type,
)
from veupath_chatbot.services.experiment.helpers import ControlsContext
from veupath_chatbot.services.experiment.materialization import (
    _materialize_step_tree,
)
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
)
from veupath_chatbot.services.experiment.types import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)
from veupath_chatbot.services.wdk.helpers import extract_record_ids

logger = get_logger(__name__)

# Skip fetching individual intersection IDs when the control set is large
# to avoid expensive WDK answer-page requests; counts alone suffice for metrics.
_MAX_CONTROL_IDS_FOR_ANSWER = 500


async def run_controls_against_tree(
    ctx: ControlsContext,
    tree: JSONObject,
) -> ControlTestResult:
    """Materialise a ``PlanStepNode`` tree, intersect with controls, return metrics.

    Creates a temporary WDK strategy containing the full tree, adds an
    intersection step with each control set on top of the root, queries the
    result counts, then deletes everything.

    Returns a :class:`ControlTestResult` so :func:`metrics_from_control_result`
    can consume it directly.
    """
    api = get_strategy_api(ctx.site_id)

    pos = [s.strip() for s in ctx.positive_controls if s.strip()]
    neg = [s.strip() for s in ctx.negative_controls if s.strip()]

    target = ControlTargetData(search_name="__tree__")
    result = ControlTestResult(
        site_id=ctx.site_id,
        record_type=ctx.record_type,
        target=target,
    )

    async def _eval_control_set(
        control_ids: list[str],
        label: str,
    ) -> JSONObject:
        """Materialise the tree, intersect with one control set, clean up."""
        root_tree = await _materialize_step_tree(
            api, tree, ctx.record_type, site_id=ctx.site_id
        )

        param_type = await resolve_controls_param_type(
            api,
            ctx.record_type,
            ctx.controls_search_name,
            ctx.controls_param_name,
        )

        controls_params: JSONObject = {}
        if param_type == "input-dataset":
            config_ds = WDKDatasetConfigIdList(
                source_type="idList",
                source_content=WDKDatasetIdListContent(ids=control_ids),
            )
            dataset_id = await api.create_dataset(config_ds)
            controls_params[ctx.controls_param_name] = str(dataset_id)
        else:
            controls_params[ctx.controls_param_name] = "\n".join(control_ids)

        controls_step = await api.create_step(
            NewStepSpec(
                search_name=ctx.controls_search_name,
                search_config=WDKSearchConfig(
                    parameters={
                        k: str(v) for k, v in controls_params.items() if v is not None
                    },
                ),
                custom_name=f"Controls ({label})",
            ),
            record_type=ctx.record_type,
        )
        controls_step_id = controls_step.id

        combined = await api.create_combined_step(
            primary_step_id=root_tree.step_id,
            secondary_step_id=controls_step_id,
            boolean_operator="INTERSECT",
            record_type=ctx.record_type,
            spec_overrides=PatchStepSpec(custom_name=f"Tree \u2229 {label}"),
        )
        combined_step_id = combined.id

        full_tree = StepTreeNode(
            step_id=combined_step_id,
            primary_input=root_tree,
            secondary_input=StepTreeNode(step_id=controls_step_id),
        )
        created = await api.create_strategy(
            step_tree=full_tree,
            name="Pathfinder tree eval",
            is_internal=True,
        )
        strategy_id = created.id

        try:
            target_total = await api.get_step_count(root_tree.step_id)
            intersection_total = await api.get_step_count(combined_step_id)

            intersection_ids: list[str] = []
            if len(control_ids) <= _MAX_CONTROL_IDS_FOR_ANSWER:
                answer = await api.get_step_answer(
                    combined_step_id,
                    pagination={
                        "offset": 0,
                        "numRecords": min(
                            len(control_ids), _MAX_CONTROL_IDS_FOR_ANSWER
                        ),
                    },
                )
                intersection_ids = extract_record_ids(answer.records)

            ids_list: JSONArray = list(intersection_ids)
            ids_sample: JSONArray = list(intersection_ids[:50])
            return {
                "controlsCount": len(control_ids),
                "intersectionCount": intersection_total,
                "intersectionIds": ids_list,
                "intersectionIdsSample": ids_sample,
                "targetStepId": root_tree.step_id,
                "targetResultCount": target_total,
            }
        finally:
            await delete_temp_strategy(api, strategy_id)

    if pos:
        pos_payload = await _eval_control_set(pos, "positive")
        pos_data = ControlSetData.model_validate(pos_payload)

        pos_count, found_ids, has_ids = _extract_intersection_data(pos_payload)
        missing = [x for x in pos if x not in found_ids] if has_ids else []

        target.result_count = pos_data.target_result_count
        pos_data.missing_ids_sample = missing[:50]
        pos_data.recall = pos_count / len(pos) if pos else None
        result.positive = pos_data

    if neg:
        neg_payload = await _eval_control_set(neg, "negative")
        neg_data = ControlSetData.model_validate(neg_payload)

        if target.result_count is None:
            target.result_count = neg_data.target_result_count

        neg_count, hit_ids, _ = _extract_intersection_data(neg_payload)
        unexpected_hits = sorted(hit_ids)[:50] if hit_ids else []
        neg_data.unexpected_hits_sample = unexpected_hits
        neg_data.false_positive_rate = neg_count / len(neg) if neg else None
        result.negative = neg_data

    return result


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


def _extract_eval_counts(result: ControlTestResult) -> _EvalCounts:
    """Pull hit counts and IDs from a control-test result."""
    pos = result.positive
    neg = result.negative

    return _EvalCounts(
        pos_hits=pos.intersection_count if pos else 0,
        pos_total=pos.controls_count if pos else 0,
        neg_hits=neg.intersection_count if neg else 0,
        neg_total=neg.controls_count if neg else 0,
        total_results=result.target.result_count or 0,
        pos_ids=list(pos.intersection_ids) if pos else [],
        neg_ids=list(neg.intersection_ids) if neg else [],
    )


def _f1_from_counts(counts: _EvalCounts) -> float:
    """Compute F1 from evaluation counts via the canonical metrics engine."""
    cm = compute_confusion_matrix(
        positive_hits=counts.pos_hits,
        total_positives=counts.pos_total,
        negative_hits=counts.neg_hits,
        total_negatives=counts.neg_total,
    )
    return compute_metrics(cm, total_results=counts.total_results).f1_score
