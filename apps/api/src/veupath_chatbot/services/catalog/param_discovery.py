"""Search details discovery with fallback scanning.

Handles fetching search details from the WDK discovery service,
including fallback scanning across all record types when the initial
fetch fails.
"""

from typing import Any, cast

import httpx

from veupath_chatbot.integrations.veupathdb.param_utils import (
    wdk_entity_name,
    wdk_search_matches,
)
from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.platform.errors import ValidationError as CoreValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue


async def fetch_search_details(
    discovery: Any,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    *,
    record_types: list[Any] | None = None,
) -> tuple[JSONObject, str]:
    """Fetch search details, falling back to scanning all record types.

    :param discovery: Discovery service instance.
    :param site_id: Site identifier.
    :param resolved_record_type: Record type to try first.
    :param search_name: Name of the search.
    :param record_types: All available record types (for fallback scan).
    :returns: Tuple of (details dict, resolved record type).
    :raises CoreValidationError: When the search cannot be found.
    """
    try:
        details = await discovery.get_search_details(
            site_id, resolved_record_type, search_name, expand_params=True
        )
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as e:
        return await _fallback_scan_record_types(
            discovery,
            site_id,
            resolved_record_type,
            search_name,
            record_types=record_types or [],
            original_error=e,
        )
    else:
        return details, resolved_record_type


async def _fallback_scan_record_types(
    discovery: Any,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    *,
    record_types: list[Any],
    original_error: Exception,
) -> tuple[JSONObject, str]:
    """Scan all record types trying to find the search, raising if not found."""
    details: JSONObject | None = None
    for rt in record_types:
        if not isinstance(rt, dict):
            continue
        rt_name = wdk_entity_name(rt)
        if not rt_name:
            continue
        searches = await discovery.get_searches(site_id, rt_name)
        if any(wdk_search_matches(s, search_name) for s in searches):
            resolved_record_type = rt_name
            try:
                details = await discovery.get_search_details(
                    site_id, rt_name, search_name, expand_params=True
                )
            except httpx.HTTPError, AppError, ValueError, TypeError, KeyError:
                details = None
            break

    if details is None:
        available = await discovery.get_searches(site_id, resolved_record_type)
        available_searches: list[str] = [
            name
            for s in available
            if isinstance(s, dict) and (name := wdk_entity_name(s))
        ]
        error_dict: JSONObject = {
            "path": "searchName",
            "message": f"Search not found: {search_name}",
            "code": ErrorCode.SEARCH_NOT_FOUND.value,
            "recordType": resolved_record_type,
            "searchName": search_name,
            "availableSearches": cast("JSONValue", available_searches),
            "details": str(original_error),
        }
        raise CoreValidationError(
            title="Search not found",
            detail=f"Search not found: {search_name}",
            errors=[error_dict],
        ) from original_error

    return details, resolved_record_type
