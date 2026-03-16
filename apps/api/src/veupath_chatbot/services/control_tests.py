"""Positive/negative control test helpers for planning mode.

These helpers run *temporary* WDK steps/strategies to evaluate whether known
positive controls are returned and known negative controls are excluded.
"""

from typing import TypedDict, cast

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.domain.strategy.ops import DEFAULT_COMBINE_OPERATOR
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue, as_json_object
from veupath_chatbot.services.control_helpers import (
    _encode_id_list,
    _get_total_count_for_step,
    cleanup_internal_control_test_strategies,
    delete_temp_strategy,
)
from veupath_chatbot.services.experiment.helpers import coerce_step_id, extract_wdk_id
from veupath_chatbot.services.experiment.types import ControlValueFormat
from veupath_chatbot.services.wdk.helpers import extract_record_ids


def _require_step_id(raw: JSONObject | None, label: str) -> int:
    """Coerce a WDK step response to an int ID, raising InternalError on failure."""
    try:
        return coerce_step_id(raw)
    except ValueError as exc:
        raise InternalError(
            title="Step creation failed",
            detail=f"WDK returned no id for {label}: {exc}",
        ) from exc


__all__ = [
    "resolve_controls_param_type",
    "_extract_intersection_data",
    "_run_intersection_control",
    "_cleanup_internal_control_test_strategies",
    "run_positive_negative_controls",
]

logger = get_logger(__name__)


class _IntersectionKwargs(TypedDict):
    """Common kwargs shared between positive and negative control runs."""

    site_id: str
    record_type: str
    target_search_name: str
    target_parameters: JSONObject
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat
    controls_extra_parameters: JSONObject | None
    boolean_operator: str
    id_field: str | None


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
        details = await api.client.get_search_details(record_type, controls_search_name)
        search_data = details.get("searchData") if isinstance(details, dict) else None
        if not isinstance(search_data, dict):
            return None
        params = search_data.get("parameters")
        if not isinstance(params, list):
            return None
        for p in params:
            if isinstance(p, dict) and p.get("name") == controls_param_name:
                ptype = p.get("type")
                return str(ptype) if ptype else None
    except Exception:
        logger.debug(
            "Could not resolve param type for controls",
            search=controls_search_name,
            param=controls_param_name,
        )
    return None


async def _run_intersection_control(
    *,
    site_id: str,
    record_type: str,
    target_search_name: str,
    target_parameters: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_ids: list[str],
    controls_value_format: ControlValueFormat,
    controls_extra_parameters: JSONObject | None,
    boolean_operator: str = DEFAULT_COMBINE_OPERATOR.value,
    fetch_ids_limit: int = 500,
    id_field: str | None = None,
) -> JSONObject:
    """Run a single control intersection and return results.

    Creates its OWN target step internally.  WDK cascade-deletes all steps
    inside a strategy when the strategy is deleted, so sharing a target step
    across multiple calls would cause the second call to fail with
    ``"<stepId> is not a valid step ID"``.
    """
    from veupath_chatbot.services.catalog.searches import find_record_type_for_search

    api = get_strategy_api(site_id)

    # Auto-resolve record types for both searches via the cached catalog.
    # The AI often passes 'gene' but VEuPathDB gene searches live under
    # 'transcript'.  The catalog knows the correct mapping.
    target_rt = await find_record_type_for_search(
        site_id, record_type, target_search_name
    )
    controls_rt = await find_record_type_for_search(
        site_id, record_type, controls_search_name
    )

    target_step = await api.create_step(
        record_type=target_rt,
        search_name=target_search_name,
        parameters=target_parameters or {},
        custom_name="Target",
    )
    target_step_id = _require_step_id(target_step, "target step")

    # Determine whether the controls parameter is an input-dataset type.
    # If so, upload the IDs as a WDK dataset and pass the dataset ID.
    param_type = await resolve_controls_param_type(
        api, controls_rt, controls_search_name, controls_param_name
    )

    controls_params = dict(controls_extra_parameters or {})
    if param_type == "input-dataset":
        dataset_id = await api.create_dataset(controls_ids)
        controls_params[controls_param_name] = str(dataset_id)
    else:
        controls_params[controls_param_name] = _encode_id_list(
            controls_ids, controls_value_format
        )

    controls_step = await api.create_step(
        record_type=controls_rt,
        search_name=controls_search_name,
        parameters=controls_params,
        custom_name="Controls",
    )
    controls_step_id = _require_step_id(controls_step, "controls step")

    combined_step = await api.create_combined_step(
        primary_step_id=target_step_id,
        secondary_step_id=controls_step_id,
        boolean_operator=boolean_operator,
        record_type=target_rt,
        custom_name=f"{boolean_operator} controls",
    )
    combined_step_id = _require_step_id(combined_step, "combined step")

    # WDK requires steps to be part of a strategy before they can be
    # queried for results (StepService enforces this).
    root = StepTreeNode(
        combined_step_id,
        primary_input=StepTreeNode(target_step_id),
        secondary_input=StepTreeNode(controls_step_id),
    )
    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=root,
            name="Pathfinder control test",
            description=None,
            is_internal=True,
        )
        temp_strategy_id = extract_wdk_id(created)

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
                (answer or {}).get("records"), preferred_key=id_field
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
    except Exception as exc:
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
    *,
    site_id: str,
    record_type: str,
    target_search_name: str,
    target_parameters: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    controls_value_format: ControlValueFormat = "newline",
    controls_extra_parameters: JSONObject | None = None,
    id_field: str | None = None,
    skip_cleanup: bool = False,
) -> JSONObject:
    """Run positive + negative controls against a single WDK question configuration.

    Each control set (positive / negative) creates its own target step
    internally.  WDK cascade-deletes all steps inside a strategy when the
    strategy is deleted, so a shared target step would be invalidated after
    the first control run's cleanup.

    :param skip_cleanup: When ``True``, skip the upfront strategy cleanup.
        Useful when the caller already performed cleanup (e.g. batch sweeps).
    """
    if not skip_cleanup:
        cleanup_api = get_strategy_api(site_id)
        await _cleanup_internal_control_test_strategies(cleanup_api)

    # Common kwargs passed to _run_intersection_control for both control sets.
    common_kwargs: _IntersectionKwargs = {
        "site_id": site_id,
        "record_type": record_type,
        "target_search_name": target_search_name,
        "target_parameters": target_parameters,
        "controls_search_name": controls_search_name,
        "controls_param_name": controls_param_name,
        "controls_value_format": controls_value_format,
        "controls_extra_parameters": controls_extra_parameters,
        "boolean_operator": DEFAULT_COMBINE_OPERATOR.value,
        "id_field": id_field,
    }

    result: JSONObject = {
        "siteId": site_id,
        "recordType": record_type,
        "target": {
            "searchName": target_search_name,
            "parameters": target_parameters or {},
            "stepId": None,
            "resultCount": None,
        },
        "positive": None,
        "negative": None,
    }

    pos = [str(x).strip() for x in (positive_controls or []) if str(x).strip()]
    neg = [str(x).strip() for x in (negative_controls or []) if str(x).strip()]

    if pos:
        pos_payload = await _run_intersection_control(
            **common_kwargs,
            controls_ids=pos,
        )
        # Capture target info from the first successful run.
        target = as_json_object(result["target"])
        target["stepId"] = pos_payload.get("targetStepId")
        target["resultCount"] = pos_payload.get("targetResultCount")

        pos_count, found_ids, has_ids = _extract_intersection_data(pos_payload)
        missing = [x for x in pos if x not in found_ids] if has_ids else []
        missing_sample = cast(JSONValue, missing[:50])
        result["positive"] = {
            **pos_payload,
            "missingIdsSample": missing_sample,
            "recall": pos_count / len(pos) if pos else None,
        }

    if neg:
        neg_payload = await _run_intersection_control(
            **common_kwargs,
            controls_ids=neg,
        )
        # Fill target info if not set yet (e.g. no positive controls).
        target = as_json_object(result["target"])
        if target.get("stepId") is None:
            target["stepId"] = neg_payload.get("targetStepId")
            target["resultCount"] = neg_payload.get("targetResultCount")

        neg_count, hit_ids, _ = _extract_intersection_data(neg_payload)
        unexpected_sample = cast(JSONValue, list(hit_ids)[:50] if hit_ids else [])
        result["negative"] = {
            **neg_payload,
            "unexpectedHitsSample": unexpected_sample,
            "falsePositiveRate": neg_count / len(neg) if neg else None,
        }

    return result
