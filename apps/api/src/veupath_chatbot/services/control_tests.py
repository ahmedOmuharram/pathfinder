"""Positive/negative control test helpers for planning mode.

These helpers run *temporary* WDK steps/strategies to evaluate whether known
positive controls are returned and known negative controls are excluded.
"""

from dataclasses import dataclass, field

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.domain.strategy.ops import DEFAULT_COMBINE_OPERATOR
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKParameter
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.catalog.searches import find_record_type_for_search
from veupath_chatbot.services.control_helpers import (
    _encode_id_list,
    _get_total_count_for_step,
    cleanup_internal_control_test_strategies,
    delete_temp_strategy,
)
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
)
from veupath_chatbot.services.experiment.types import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
    ControlValueFormat,
    ExperimentConfig,
)
from veupath_chatbot.services.wdk.helpers import extract_record_ids

__all__ = [
    "IntersectionConfig",
    "_cleanup_internal_control_test_strategies",
    "_extract_intersection_data",
    "_run_intersection_control",
    "resolve_controls_param_type",
    "run_positive_negative_controls",
]

logger = get_logger(__name__)


@dataclass
class IntersectionConfig:
    """Configuration for a single control-test intersection run.

    Groups the parameters that define the WDK search target and the controls
    search configuration.  Passed as a single argument to
    :func:`_run_intersection_control` and :func:`run_positive_negative_controls`
    to keep their signatures concise.
    """

    site_id: str
    record_type: str
    target_search_name: str
    target_parameters: JSONObject
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat = "newline"
    controls_extra_parameters: JSONObject | None = None
    boolean_operator: str = field(
        default_factory=lambda: DEFAULT_COMBINE_OPERATOR.value
    )
    id_field: str | None = None

    @classmethod
    def from_experiment_config(
        cls,
        config: ExperimentConfig,
        *,
        target_parameters: JSONObject | None = None,
    ) -> "IntersectionConfig":
        """Build an IntersectionConfig from an ExperimentConfig.

        :param config: The experiment configuration.
        :param target_parameters: Override for ``config.parameters`` (e.g.
            when evaluating modified/optimized parameters).
        """
        return cls(
            site_id=config.site_id,
            record_type=config.record_type,
            target_search_name=config.search_name,
            target_parameters=(
                target_parameters
                if target_parameters is not None
                else config.parameters
            ),
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            controls_value_format=config.controls_value_format,
        )

    @classmethod
    def from_controls_context(
        cls,
        ctx: ControlsContext,
        *,
        target_search_name: str,
        target_parameters: JSONObject,
        controls_extra_parameters: JSONObject | None = None,
        id_field: str | None = None,
    ) -> "IntersectionConfig":
        """Build an IntersectionConfig from a ControlsContext.

        :param ctx: The controls context (provides site, record type, and
            controls search configuration).
        :param target_search_name: WDK search name for the target step.
        :param target_parameters: WDK parameters for the target step.
        :param controls_extra_parameters: Extra parameters for the controls
            search (e.g. organism scope).
        :param id_field: Override for the gene-ID field name.
        """
        return cls(
            site_id=ctx.site_id,
            record_type=ctx.record_type,
            target_search_name=target_search_name,
            target_parameters=target_parameters,
            controls_search_name=ctx.controls_search_name,
            controls_param_name=ctx.controls_param_name,
            controls_value_format=ctx.controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=id_field,
        )


def _find_param_type(params: list[WDKParameter], param_name: str) -> str | None:
    """Find the type of a named parameter in a WDK parameters list."""
    for p in params:
        if p.name == param_name:
            return p.type
    return None


async def resolve_controls_param_type(
    api: StrategyAPI,
    record_type: str,
    controls_search_name: str,
    controls_param_name: str,
) -> str | None:
    """Return the WDK param type for a controls parameter.

    :param api: Strategy API instance.
    :param record_type: WDK record type.
    :param controls_search_name: Name of the controls search.
    :param controls_param_name: Parameter name within the controls search.
    :returns: Parameter type string (e.g. ``"input-dataset"``) or None.
    """
    try:
        response = await api.client.get_search_details(
            record_type, controls_search_name
        )
        params = response.search_data.parameters
        if params is not None:
            return _find_param_type(params, controls_param_name)
    except AppError as exc:
        logger.warning(
            "Could not resolve param type for controls",
            search=controls_search_name,
            param=controls_param_name,
            record_type=record_type,
            error=str(exc),
        )
    return None


async def _run_intersection_control(
    config: IntersectionConfig,
    controls_ids: list[str],
    fetch_ids_limit: int = 500,
) -> JSONObject:
    """Run a single control intersection and return results.

    Creates its OWN target step internally.  WDK cascade-deletes all steps
    inside a strategy when the strategy is deleted, so sharing a target step
    across multiple calls would cause the second call to fail with
    ``"<stepId> is not a valid step ID"``.
    """
    api = get_strategy_api(config.site_id)

    # Auto-resolve record types for both searches via the cached catalog.
    # The AI often passes 'gene' but VEuPathDB gene searches live under
    # 'transcript'.  The catalog knows the correct mapping.
    target_rt = await find_record_type_for_search(
        SearchContext(config.site_id, config.record_type, config.target_search_name)
    )
    controls_rt = await find_record_type_for_search(
        SearchContext(config.site_id, config.record_type, config.controls_search_name)
    )

    target_step = await api.create_step(
        NewStepSpec(
            search_name=config.target_search_name,
            search_config=WDKSearchConfig(
                parameters={
                    k: str(v)
                    for k, v in (config.target_parameters or {}).items()
                    if v is not None
                },
            ),
            custom_name="Target",
        ),
        record_type=target_rt,
    )
    target_step_id = target_step.id

    # Determine whether the controls parameter is an input-dataset type.
    # If so, upload the IDs as a WDK dataset and pass the dataset ID.
    param_type = await resolve_controls_param_type(
        api, controls_rt, config.controls_search_name, config.controls_param_name
    )

    controls_params = dict(config.controls_extra_parameters or {})
    if param_type == "input-dataset":
        config_ds = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=controls_ids),
        )
        dataset_id = await api.create_dataset(config_ds)
        controls_params[config.controls_param_name] = str(dataset_id)
    else:
        controls_params[config.controls_param_name] = _encode_id_list(
            controls_ids, config.controls_value_format
        )

    controls_step = await api.create_step(
        NewStepSpec(
            search_name=config.controls_search_name,
            search_config=WDKSearchConfig(
                parameters={
                    k: str(v) for k, v in controls_params.items() if v is not None
                },
            ),
            custom_name="Controls",
        ),
        record_type=controls_rt,
    )
    controls_step_id = controls_step.id

    combined_step = await api.create_combined_step(
        primary_step_id=target_step_id,
        secondary_step_id=controls_step_id,
        boolean_operator=config.boolean_operator,
        record_type=target_rt,
        spec_overrides=PatchStepSpec(custom_name=f"{config.boolean_operator} controls"),
    )
    combined_step_id = combined_step.id

    # WDK requires steps to be part of a strategy before they can be
    # queried for results (StepService enforces this).
    root = WDKStepTree(
        step_id=combined_step_id,
        primary_input=WDKStepTree(step_id=target_step_id),
        secondary_input=WDKStepTree(step_id=controls_step_id),
    )
    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=root,
            name="Pathfinder control test",
            description=None,
            is_internal=True,
        )
        temp_strategy_id = created.id

        # Now the steps ARE part of a strategy → we can query them.
        target_total = await _get_total_count_for_step(api, target_step_id)
        total = await _get_total_count_for_step(api, combined_step_id)
        ids_found: list[str] = []
        if controls_ids and len(controls_ids) <= fetch_ids_limit:
            answer = await api.get_step_answer(
                combined_step_id,
                pagination={
                    "offset": 0,
                    "numRecords": min(len(controls_ids), fetch_ids_limit),
                },
            )
            ids_found = extract_record_ids(
                answer.records, preferred_key=config.id_field
            )

        # Convert list[str] to JSONValue-compatible types
        intersection_ids_sample: JSONValue = list(ids_found[:50])
        intersection_ids: JSONValue = (
            list(ids_found) if len(controls_ids) <= fetch_ids_limit else None
        )
        return {
            "controlsCount": len([x for x in controls_ids if str(x).strip()]),
            "intersectionCount": total,
            "intersectionIdsSample": intersection_ids_sample,
            "intersectionIds": intersection_ids,
            "targetStepId": target_step_id,
            "targetResultCount": target_total,
        }
    finally:
        await delete_temp_strategy(api, temp_strategy_id)


async def _cleanup_internal_control_test_strategies(api: StrategyAPI) -> None:
    """Best-effort cleanup of leaked internal control-test strategies.

    Control-test runs create temporary WDK strategies under the current user
    account. They are deleted at the end of each run, but interrupted requests
    (tab close, timeout, network errors) can leave internal drafts behind.
    """
    try:
        strategies = await api.list_strategies()
    except AppError as exc:
        logger.warning(
            "Failed to list strategies for control-test cleanup", error=str(exc)
        )
        return
    await cleanup_internal_control_test_strategies(api, strategies)


def _extract_intersection_data(
    payload: JSONObject,
) -> tuple[int, set[str], bool]:
    """Extract intersection count and ID set from a control-test payload.

    :returns: ``(count, id_set, has_id_list)`` where *has_id_list* indicates
        whether the payload contained an explicit intersection IDs list
        (``False`` when there are >500 controls and IDs weren't fetched).
    """
    raw_count = payload.get("intersectionCount")
    count = int(raw_count) if isinstance(raw_count, (int, float)) else 0

    ids_value = payload.get("intersectionIds") if isinstance(payload, dict) else None
    id_set: set[str] = set()
    if isinstance(ids_value, list):
        id_set = {str(x) for x in ids_value if x is not None}
    return count, id_set, isinstance(ids_value, list)


async def run_positive_negative_controls(
    config: IntersectionConfig,
    *,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    skip_cleanup: bool = False,
) -> ControlTestResult:
    """Run positive + negative controls against a single WDK question configuration.

    Each control set (positive / negative) creates its own target step
    internally.  WDK cascade-deletes all steps inside a strategy when the
    strategy is deleted, so a shared target step would be invalidated after
    the first control run's cleanup.

    :param config: Intersection configuration (site, record type, search names, etc.).
    :param positive_controls: Known-positive IDs that should be returned.
    :param negative_controls: Known-negative IDs that should NOT be returned.
    :param skip_cleanup: When ``True``, skip the upfront strategy cleanup.
        Useful when the caller already performed cleanup (e.g. batch sweeps).
    """
    if not skip_cleanup:
        cleanup_api = get_strategy_api(config.site_id)
        await _cleanup_internal_control_test_strategies(cleanup_api)

    target = ControlTargetData(
        search_name=config.target_search_name,
        parameters=config.target_parameters or {},
    )
    result = ControlTestResult(
        site_id=config.site_id,
        record_type=config.record_type,
        target=target,
    )

    pos = [str(x).strip() for x in (positive_controls or []) if str(x).strip()]
    neg = [str(x).strip() for x in (negative_controls or []) if str(x).strip()]

    if pos:
        pos_payload = await _run_intersection_control(config, controls_ids=pos)
        pos_data = ControlSetData.model_validate(pos_payload)

        # Capture target info from the first successful run.
        target.step_id = pos_data.target_step_id
        target.result_count = pos_data.target_result_count

        pos_count, found_ids, has_ids = _extract_intersection_data(pos_payload)
        missing = [x for x in pos if x not in found_ids] if has_ids else []
        pos_data.missing_ids_sample = missing[:50]
        pos_data.recall = pos_count / len(pos) if pos else None
        result.positive = pos_data

    if neg:
        neg_payload = await _run_intersection_control(config, controls_ids=neg)
        neg_data = ControlSetData.model_validate(neg_payload)

        # Fill target info if not set yet (e.g. no positive controls).
        if target.step_id is None:
            target.step_id = neg_data.target_step_id
            target.result_count = neg_data.target_result_count

        neg_count, hit_ids, _ = _extract_intersection_data(neg_payload)
        unexpected_hits = sorted(hit_ids)[:50] if hit_ids else []
        neg_data.unexpected_hits_sample = unexpected_hits
        neg_data.false_positive_rate = neg_count / len(neg) if neg else None
        result.negative = neg_data

    return result
