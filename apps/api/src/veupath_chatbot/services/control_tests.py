"""Positive/negative control test helpers for planning mode.

These helpers run *temporary* WDK steps/strategies to evaluate whether known
positive controls are returned and known negative controls are excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode


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


def _coerce_step_id(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("stepId", "step_id", "id"):
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _extract_record_ids(records: Any, *, preferred_key: str | None = None) -> list[str]:
    """Best-effort extraction of record IDs from WDK answer records."""
    if not isinstance(records, list):
        return []
    keys_to_try = []
    if preferred_key:
        keys_to_try.append(preferred_key)
    keys_to_try.extend(
        [
            "primaryKey",
            "primary_key",
            "recordId",
            "record_id",
            "source_id",
            "sourceId",
            "id",
        ]
    )
    out: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        value = None
        for k in keys_to_try:
            if k in rec:
                value = rec.get(k)
                break
        if value is None:
            # Some WDK answers nest attributes.
            attrs = rec.get("attributes")
            if isinstance(attrs, dict):
                for k in keys_to_try:
                    if k in attrs:
                        value = attrs.get(k)
                        break
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out.append(text)
    return out


async def _get_total_count_for_step(api, step_id: int) -> int | None:
    try:
        answer = await api.get_step_answer(step_id, pagination={"offset": 0, "numRecords": 0})
        if isinstance(answer, dict):
            meta = answer.get("meta") or {}
            raw = meta.get("totalCount")
            if raw is None:
                return None
            return int(raw)
    except Exception:
        return None
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
    controls_extra_parameters: dict[str, Any] | None,
    boolean_operator: str = "INTERSECT",
    fetch_ids_limit: int = 500,
    id_field: str | None = None,
) -> dict[str, Any]:
    api = get_strategy_api(site_id)

    controls_params = dict(controls_extra_parameters or {})
    controls_params[controls_param_name] = _encode_id_list(controls_ids, controls_value_format)

    controls_step = await api.create_step(
        record_type=record_type,
        search_name=controls_search_name,
        parameters=controls_params,
        custom_name="Controls",
    )
    controls_step_id = _coerce_step_id(controls_step)
    if controls_step_id is None:
        raise RuntimeError("Failed to create controls step (missing stepId).")

    combined_step = await api.create_combined_step(
        primary_step_id=target_step_id,
        secondary_step_id=controls_step_id,
        boolean_operator=boolean_operator,
        record_type=record_type,
        custom_name=f"{boolean_operator} controls",
    )
    combined_step_id = _coerce_step_id(combined_step)
    if combined_step_id is None:
        raise RuntimeError("Failed to create combined step (missing stepId).")

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
        raw_sid = (created or {}).get("id") or (created or {}).get("strategyId")
        if raw_sid is not None:
            try:
                temp_strategy_id = int(raw_sid)
            except (TypeError, ValueError):
                temp_strategy_id = None

        total = await _get_total_count_for_step(api, combined_step_id)
        ids_found: list[str] = []
        if controls_ids and len(controls_ids) <= fetch_ids_limit:
            answer = await api.get_step_answer(
                combined_step_id,
                pagination={"offset": 0, "numRecords": min(len(controls_ids), fetch_ids_limit)},
            )
            ids_found = _extract_record_ids((answer or {}).get("records"), preferred_key=id_field)

        return {
            "controlsCount": len([x for x in controls_ids if str(x).strip()]),
            "intersectionCount": total,
            "intersectionIdsSample": ids_found[:50],
            "intersectionIds": ids_found if len(controls_ids) <= fetch_ids_limit else None,
        }
    finally:
        if temp_strategy_id is not None:
            try:
                await api.delete_strategy(temp_strategy_id)
            except Exception:
                pass


async def run_positive_negative_controls(
    *,
    site_id: str,
    record_type: str,
    target_search_name: str,
    target_parameters: dict[str, Any],
    controls_search_name: str,
    controls_param_name: str,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    controls_value_format: ControlValueFormat = "newline",
    controls_extra_parameters: dict[str, Any] | None = None,
    id_field: str | None = None,
) -> dict[str, Any]:
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
        raise RuntimeError("Failed to create target step (missing stepId).")

    target_total = await _get_total_count_for_step(api, target_step_id)

    result: dict[str, Any] = {
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
        found_ids = set((pos_payload.get("intersectionIds") or []) if isinstance(pos_payload, dict) else [])
        missing = [x for x in pos if found_ids and x not in found_ids]
        result["positive"] = {
            **pos_payload,
            "missingIdsSample": missing[:50] if missing else [],
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
        hit_ids = set((neg_payload.get("intersectionIds") or []) if isinstance(neg_payload, dict) else [])
        result["negative"] = {
            **neg_payload,
            "unexpectedHitsSample": list(hit_ids)[:50] if hit_ids else [],
            "falsePositiveRate": (len(hit_ids) / len(neg)) if hit_ids else None,
        }

    return result

