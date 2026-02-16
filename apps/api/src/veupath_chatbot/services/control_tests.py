"""Positive/negative control test helpers for planning mode.

These helpers run *temporary* WDK steps/strategies to evaluate whether known
positive controls are returned and known negative controls are excluded.
"""

from __future__ import annotations

from typing import Literal

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StepTreeNode,
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue, as_json_object

logger = get_logger(__name__)

ControlValueFormat = Literal["newline", "json_list", "comma"]


def _encode_id_list(ids: list[str], fmt: ControlValueFormat) -> str:
    cleaned = [str(x).strip() for x in ids if str(x).strip()]
    if fmt == "newline":
        return "\n".join(cleaned)
    if fmt == "comma":
        return ",".join(cleaned)
    # json_list
    import json

    return json.dumps(cleaned)


def _coerce_step_id(payload: JSONObject | None) -> int | None:
    """Extract the step ID from a WDK step-creation response.

    WDK ``StepFormatter`` emits the step ID under ``JsonKeys.ID = "id"``
    as a Java long (always int in JSON).

    :param payload: WDK step-creation response.
    :returns: Step ID or None.
    """
    if not isinstance(payload, dict):
        return None
    raw = payload.get("id")
    if isinstance(raw, int):
        return raw
    return None


def _extract_record_ids(
    records: JSONValue, *, preferred_key: str | None = None
) -> list[str]:
    """Extract record IDs from WDK answer records.

    WDK's ``StandardReporter`` formats each record with:
    - ``id``: array of ``{name, value}`` pairs (composite PK) — note: this
      is ``"id"``, **not** ``"primaryKey"`` (a common confusion).
    - ``attributes``: dict of attributeName → value

    If ``preferred_key`` is given, look it up in ``attributes`` first.
    Otherwise, extract the first ``id`` (primary key) value.

    :param records: WDK answer records.
    :param preferred_key: Preferred attribute key (default: None).
    :returns: List of record IDs.
    """
    if not isinstance(records, list):
        return []
    out: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        extracted: str | None = None

        # 1) If caller specified a preferred attribute, look there.
        if preferred_key:
            attrs = rec.get("attributes")
            if isinstance(attrs, dict):
                val = attrs.get(preferred_key)
                if isinstance(val, str) and val.strip():
                    extracted = val.strip()

        # 2) Fall back to the primary-key array (WDK uses "id").
        if extracted is None:
            pk = rec.get("id")
            if isinstance(pk, list) and pk:
                first_pk = pk[0]
                if isinstance(first_pk, dict):
                    val = first_pk.get("value")
                    if isinstance(val, str) and val.strip():
                        extracted = val.strip()

        if extracted:
            out.append(extracted)
    return out


async def _get_total_count_for_step(api: StrategyAPI, step_id: int) -> int | None:
    """Get totalCount for a step. Returns None on failure."""
    try:
        return await api.get_step_count(step_id)
    except Exception:
        return None


async def _resolve_controls_param_type(
    api: StrategyAPI,
    record_type: str,
    controls_search_name: str,
    controls_param_name: str,
) -> str | None:
    """Return the WDK param type for the controls parameter, or None on failure."""
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
    boolean_operator: str = "INTERSECT",
    fetch_ids_limit: int = 500,
    id_field: str | None = None,
) -> JSONObject:
    """Run a single control intersection and return results.

    Creates its OWN target step internally.  WDK cascade-deletes all steps
    inside a strategy when the strategy is deleted, so sharing a target step
    across multiple calls would cause the second call to fail with
    ``"<stepId> is not a valid step ID"``.
    """
    api = get_strategy_api(site_id)
    await _cleanup_internal_control_test_strategies(api)

    target_step = await api.create_step(
        record_type=record_type,
        search_name=target_search_name,
        parameters=target_parameters or {},
        custom_name="Target",
    )
    target_step_id = _coerce_step_id(target_step)
    if target_step_id is None:
        raise InternalError(
            title="Control test failed",
            detail="Failed to create target step (missing id).",
        )

    # Determine whether the controls parameter is an input-dataset type.
    # If so, upload the IDs as a WDK dataset and pass the dataset ID.
    param_type = await _resolve_controls_param_type(
        api, record_type, controls_search_name, controls_param_name
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
        record_type=record_type,
        search_name=controls_search_name,
        parameters=controls_params,
        custom_name="Controls",
    )
    controls_step_id = _coerce_step_id(controls_step)
    if controls_step_id is None:
        raise InternalError(
            title="Control test failed",
            detail="Failed to create controls step (missing id).",
        )

    combined_step = await api.create_combined_step(
        primary_step_id=target_step_id,
        secondary_step_id=controls_step_id,
        boolean_operator=boolean_operator,
        record_type=record_type,
        custom_name=f"{boolean_operator} controls",
    )
    combined_step_id = _coerce_step_id(combined_step)
    if combined_step_id is None:
        raise InternalError(
            title="Control test failed",
            detail="Failed to create combined step (missing id).",
        )

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
        # WDK StrategyService.createStrategy returns { "id": <strategyId> }.
        if isinstance(created, dict):
            raw_sid = created.get("id")
            if isinstance(raw_sid, int):
                temp_strategy_id = raw_sid

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
            ids_found = _extract_record_ids(
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
        # Strategy deletion cascade-deletes all steps inside it, which is
        # why each call creates its own target step.
        if temp_strategy_id is not None:
            try:
                await api.delete_strategy(temp_strategy_id)
            except Exception as e:
                logger.warning(
                    "Failed to delete temp WDK strategy during cleanup",
                    temp_strategy_id=temp_strategy_id,
                    error=str(e),
                )


async def _cleanup_internal_control_test_strategies(api: StrategyAPI) -> None:
    """Best-effort cleanup of leaked internal control-test strategies.

    Control-test runs create temporary WDK strategies under the current user
    account. They are deleted at the end of each run, but interrupted requests
    (tab close, timeout, network errors) can leave internal drafts behind.
    """
    try:
        strategies = await api.list_strategies()
    except Exception:
        return
    if not isinstance(strategies, list):
        return

    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        name_raw = strategy.get("name")
        if not isinstance(name_raw, str):
            continue
        if not is_internal_wdk_strategy_name(name_raw):
            continue
        display_name = strip_internal_wdk_strategy_name(name_raw)
        if not display_name.startswith("Pathfinder control test"):
            continue

        strategy_id_raw = strategy.get("strategyId")
        if not isinstance(strategy_id_raw, int):
            continue
        try:
            await api.delete_strategy(strategy_id_raw)
        except Exception as e:
            logger.warning(
                "Failed to delete stale internal control-test strategy",
                strategy_id=strategy_id_raw,
                error=str(e),
            )


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
) -> JSONObject:
    """Run positive + negative controls against a single WDK question configuration.

    Each control set (positive / negative) creates its own target step
    internally.  WDK cascade-deletes all steps inside a strategy when the
    strategy is deleted, so a shared target step would be invalidated after
    the first control run's cleanup.
    """
    # Common kwargs passed to _run_intersection_control for both control sets.
    common_kwargs: JSONObject = {
        "site_id": site_id,
        "record_type": record_type,
        "target_search_name": target_search_name,
        "target_parameters": target_parameters,
        "controls_search_name": controls_search_name,
        "controls_param_name": controls_param_name,
        "controls_value_format": controls_value_format,
        "controls_extra_parameters": controls_extra_parameters,
        "boolean_operator": "INTERSECT",
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
            **common_kwargs,  # type: ignore[arg-type]
            controls_ids=pos,
        )
        # Capture target info from the first successful run.
        target = as_json_object(result["target"])
        target["stepId"] = pos_payload.get("targetStepId")
        target["resultCount"] = pos_payload.get("targetResultCount")

        # Use intersectionCount (authoritative from WDK step count API)
        # for recall computation.  intersectionIds (extracted from the
        # answer body) may be empty when the record format doesn't match
        # _extract_record_ids expectations.
        raw_pos_count = pos_payload.get("intersectionCount")
        pos_intersection_count = (
            int(raw_pos_count) if isinstance(raw_pos_count, (int, float)) else 0
        )

        # Still attempt to extract IDs for the "missing" sample.
        intersection_ids_value = (
            pos_payload.get("intersectionIds")
            if isinstance(pos_payload, dict)
            else None
        )
        pos_intersection_ids_list: list[str] = []
        if isinstance(intersection_ids_value, list):
            pos_intersection_ids_list = [
                str(x) for x in intersection_ids_value if x is not None
            ]
        found_ids = set(pos_intersection_ids_list)
        missing = [x for x in pos if found_ids and x not in found_ids]
        missing_ids_sample: JSONValue = list(missing[:50]) if missing else []
        result["positive"] = {
            **pos_payload,
            "missingIdsSample": missing_ids_sample,
            "recall": pos_intersection_count / len(pos) if pos else None,
        }

    if neg:
        neg_payload = await _run_intersection_control(
            **common_kwargs,  # type: ignore[arg-type]
            controls_ids=neg,
        )
        # Fill target info if not set yet (e.g. no positive controls).
        target = as_json_object(result["target"])
        if target.get("stepId") is None:
            target["stepId"] = neg_payload.get("targetStepId")
            target["resultCount"] = neg_payload.get("targetResultCount")

        # Use intersectionCount (authoritative) for FPR computation.
        raw_neg_count = neg_payload.get("intersectionCount")
        neg_intersection_count = (
            int(raw_neg_count) if isinstance(raw_neg_count, (int, float)) else 0
        )

        # Still attempt to extract IDs for the "unexpected hits" sample.
        intersection_ids_value = (
            neg_payload.get("intersectionIds")
            if isinstance(neg_payload, dict)
            else None
        )
        neg_intersection_ids_list: list[str] = []
        if isinstance(intersection_ids_value, list):
            neg_intersection_ids_list = [
                str(x) for x in intersection_ids_value if x is not None
            ]
        hit_ids = set(neg_intersection_ids_list)
        unexpected_hits_sample: JSONValue = list(list(hit_ids)[:50]) if hit_ids else []
        result["negative"] = {
            **neg_payload,
            "unexpectedHitsSample": unexpected_hits_sample,
            "falsePositiveRate": neg_intersection_count / len(neg) if neg else None,
        }

    return result
