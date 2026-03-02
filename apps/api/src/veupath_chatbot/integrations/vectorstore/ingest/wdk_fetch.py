from __future__ import annotations

from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    _unwrap_search_data,
)
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


async def fetch_record_types_and_searches(
    client: VEuPathDBClient,
) -> tuple[JSONArray, list[tuple[str, JSONObject]]]:
    raw_record_types = await client.get_record_types(expanded=True)
    if isinstance(raw_record_types, dict):
        raw_record_types = (
            raw_record_types.get("recordTypes")
            or raw_record_types.get("records")
            or raw_record_types.get("result")
            or []
        )

    record_types: JSONArray = []
    searches_to_fetch: list[tuple[str, JSONObject]] = []

    for rt in raw_record_types or []:
        searches: JSONArray = []
        if isinstance(rt, str):
            rt_name = rt
        elif isinstance(rt, dict):
            rt_name = str(rt.get("urlSegment") or rt.get("name") or "").strip()
            searches_raw = rt.get("searches")
            searches = searches_raw if isinstance(searches_raw, list) else []
        else:
            continue

        if not rt_name:
            continue

        record_types.append(rt)

        if isinstance(searches, list) and searches:
            for s in searches:
                if isinstance(s, dict):
                    searches_to_fetch.append((rt_name, s))
        else:
            try:
                searches_raw = await client.get_searches(rt_name)
                searches = searches_raw if isinstance(searches_raw, list) else []
            except Exception:
                searches = []
            for s in searches or []:
                if isinstance(s, dict):
                    searches_to_fetch.append((rt_name, s))

    return record_types, searches_to_fetch


async def fetch_search_details(
    client: VEuPathDBClient,
    rt_name: str,
    search_name: str,
    summary_unwrapped: JSONObject,
) -> tuple[JSONObject, str | None]:
    details_error: str | None = None
    details_unwrapped: JSONObject = {}
    try:
        has_param_defs = any(
            k in summary_unwrapped
            for k in ("parameters", "paramSpecs", "parameterSpecs")
        ) or (
            isinstance(summary_unwrapped.get("searchData"), dict)
            and isinstance(summary_unwrapped["searchData"], dict)
            and any(
                k in summary_unwrapped["searchData"]
                for k in ("parameters", "paramSpecs", "parameterSpecs")
            )
        )
        param_names = summary_unwrapped.get("paramNames")
        if has_param_defs or (isinstance(param_names, list) and len(param_names) == 0):
            details_unwrapped = summary_unwrapped
        else:
            details = await client.get_search_details(
                rt_name, search_name, expand_params=True
            )
            details_unwrapped = _unwrap_search_data(
                details if isinstance(details, dict) else {}
            )
    except Exception as exc:
        details_error = str(exc)
        details_unwrapped = {}

    return details_unwrapped, details_error
