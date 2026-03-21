import httpx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


def _collect_dict_items(items: JSONArray) -> list[tuple[str, JSONObject]]:
    """Extract (rt_name, search_dict) pairs from a list of search-like dicts."""
    return [
        (rt_name, s)
        for s in items
        if isinstance(s, dict) and (rt_name := wdk_entity_name(s))
    ]


async def _fetch_searches_for_rt(client: VEuPathDBClient, rt_name: str) -> JSONArray:
    """Fetch searches for a record type, returning [] on error."""
    try:
        searches = await client.get_searches(rt_name)
        return [s.model_dump(by_alias=True) for s in searches]
    except httpx.HTTPError, OSError, RuntimeError:
        return []


def _process_record_type(
    rt: object,
) -> tuple[str, JSONArray] | None:
    """Extract rt_name and inline searches from a record type entry.

    Returns None if the entry should be skipped.
    """
    if isinstance(rt, str):
        return rt, []
    if isinstance(rt, dict):
        rt_name = wdk_entity_name(rt)
        if not rt_name:
            return None
        searches_raw = rt.get("searches")
        searches: JSONArray = searches_raw if isinstance(searches_raw, list) else []
        return rt_name, searches
    return None


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
        result = _process_record_type(rt)
        if result is None:
            continue
        rt_name, searches = result
        record_types.append(rt)

        if isinstance(searches, list) and searches:
            searches_to_fetch.extend(
                (rt_name, s) for s in searches if isinstance(s, dict)
            )
        else:
            fetched = await _fetch_searches_for_rt(client, rt_name)
            searches_to_fetch.extend(
                (rt_name, s) for s in fetched if isinstance(s, dict)
            )

    return record_types, searches_to_fetch


async def fetch_search_details(
    client: VEuPathDBClient,
    rt_name: str,
    search_name: str,
    summary: WDKSearch | JSONObject,
) -> tuple[JSONObject, str | None]:
    details_error: str | None = None
    details_dict: JSONObject = {}
    try:
        if isinstance(summary, WDKSearch):
            if summary.parameters is not None:
                details_dict = summary.model_dump(by_alias=True)
            else:
                response = await client.get_search_details(
                    rt_name, search_name, expand_params=True
                )
                details_dict = response.search_data.model_dump(by_alias=True)
        else:
            # Legacy dict path — check if it already has params
            has_params = any(
                k in summary for k in ("parameters", "paramSpecs", "parameterSpecs")
            )
            param_names = summary.get("paramNames")
            if has_params or (isinstance(param_names, list) and len(param_names) == 0):
                details_dict = summary
            else:
                response = await client.get_search_details(
                    rt_name, search_name, expand_params=True
                )
                details_dict = response.search_data.model_dump(by_alias=True)
    except (httpx.HTTPError, OSError, RuntimeError, AppError) as exc:
        details_error = str(exc)
        details_dict = {}

    return details_dict, details_error
