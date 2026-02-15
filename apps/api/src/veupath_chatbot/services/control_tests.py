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
)
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

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

    WDK records have:
    - ``primaryKey``: array of ``{name, value}`` pairs (composite PK)
    - ``attributes``: dict of attributeName → value

    If ``preferred_key`` is given, look it up in ``attributes`` first.
    Otherwise, extract the first ``primaryKey`` value.
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

        # 2) Fall back to first primaryKey value.
        if extracted is None:
            pk = rec.get("primaryKey")
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
    """Get totalCount from a step answer's meta. Returns None on failure."""
    try:
        answer = await api.get_step_answer(
            step_id, pagination={"offset": 0, "numRecords": 0}
        )
        if not isinstance(answer, dict):
            return None
        # WDK answer responses have JsonKeys.META → JsonKeys.TOTAL_COUNT.
        meta_raw = answer.get("meta")
        if not isinstance(meta_raw, dict):
            return None
        total = meta_raw.get("totalCount")
        return total if isinstance(total, int) else None
    except Exception:
        return None


async def _run_intersection_control(
    *,
    site_id: str,
    record_type: str,
    target_step_id: int,
    controls_search_name: str,
    controls_param_name: str,
    controls_ids: list[str],
    controls_value_format: ControlValueFormat,
    controls_extra_parameters: JSONObject | None,
    boolean_operator: str = "INTERSECT",
    fetch_ids_limit: int = 500,
    id_field: str | None = None,
) -> JSONObject:
    api = get_strategy_api(site_id)

    controls_params = dict(controls_extra_parameters or {})
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

    # Wire the combined step inputs via a temporary internal strategy.
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
        }
    finally:
        if temp_strategy_id is not None:
            try:
                await api.delete_strategy(temp_strategy_id)
            except Exception as e:
                logger.warning(
                    "Failed to delete temp WDK strategy during cleanup",
                    temp_strategy_id=temp_strategy_id,
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
    """Run positive + negative controls against a single WDK question configuration."""
    api = get_strategy_api(site_id)

    target_step = await api.create_step(
        record_type=record_type,
        search_name=target_search_name,
        parameters=target_parameters or {},
        custom_name="Target",
    )
    target_step_id = _coerce_step_id(target_step)
    if target_step_id is None:
        raise RuntimeError("Failed to create target step (missing id).")

    target_total = await _get_total_count_for_step(api, target_step_id)

    result: JSONObject = {
        "siteId": site_id,
        "recordType": record_type,
        "target": {
            "searchName": target_search_name,
            "parameters": target_parameters or {},
            "stepId": target_step_id,
            "resultCount": target_total,
        },
        "positive": None,
        "negative": None,
    }

    pos = [str(x).strip() for x in (positive_controls or []) if str(x).strip()]
    neg = [str(x).strip() for x in (negative_controls or []) if str(x).strip()]

    if pos:
        pos_payload = await _run_intersection_control(
            site_id=site_id,
            record_type=record_type,
            target_step_id=target_step_id,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_ids=pos,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            boolean_operator="INTERSECT",
            id_field=id_field,
        )
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
            "recall": (len(found_ids) / len(pos)) if found_ids else None,
        }

    if neg:
        neg_payload = await _run_intersection_control(
            site_id=site_id,
            record_type=record_type,
            target_step_id=target_step_id,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_ids=neg,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            boolean_operator="INTERSECT",
            id_field=id_field,
        )
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
            "falsePositiveRate": (len(hit_ids) / len(neg)) if hit_ids else None,
        }

    return result
