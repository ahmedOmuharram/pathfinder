"""Formatting and parsing utilities for control-test evaluation."""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import ControlValueFormat


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
