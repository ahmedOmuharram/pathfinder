"""Search details discovery with fallback scanning.

Handles fetching search details from the WDK discovery service,
including fallback scanning across all record types when the initial
fetch fails.
"""

from typing import Any, cast

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import (
    AppError,
    ErrorCode,
)
from veupath_chatbot.platform.errors import ValidationError as CoreValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue


async def fetch_search_details(
    discovery: Any,
    ctx: SearchContext,
    *,
    record_types: list[WDKRecordType] | None = None,
) -> tuple[WDKSearchResponse, str]:
    """Fetch search details, falling back to scanning all record types.

    :param discovery: Discovery service instance.
    :param ctx: Search context (site_id + record_type + search_name).
    :param record_types: All available record types (for fallback scan).
    :returns: Tuple of (WDKSearchResponse, resolved record type).
    :raises CoreValidationError: When the search cannot be found.
    """
    try:
        response = await discovery.get_search_details(ctx, expand_params=True)
    except AppError as e:
        return await _fallback_scan_record_types(
            discovery,
            ctx,
            record_types=record_types or [],
            original_error=e,
        )
    else:
        return response, ctx.record_type


async def _fallback_scan_record_types(
    discovery: Any,
    ctx: SearchContext,
    *,
    record_types: list[WDKRecordType],
    original_error: Exception,
) -> tuple[WDKSearchResponse, str]:
    """Scan all record types trying to find the search, raising if not found."""
    response: WDKSearchResponse | None = None
    resolved_record_type = ctx.record_type
    for rt in record_types:
        rt_name = rt.url_segment
        if not rt_name:
            continue
        searches = await discovery.get_searches(ctx.site_id, rt_name)
        if any(s.url_segment == ctx.search_name for s in searches):
            resolved_record_type = rt_name
            try:
                rt_ctx = SearchContext(ctx.site_id, rt_name, ctx.search_name)
                response = await discovery.get_search_details(
                    rt_ctx, expand_params=True
                )
            except AppError:
                response = None
            break

    if response is None:
        available = await discovery.get_searches(ctx.site_id, resolved_record_type)
        available_searches: list[str] = [s.url_segment for s in available]
        error_dict: JSONObject = {
            "path": "searchName",
            "message": f"Search not found: {ctx.search_name}",
            "code": ErrorCode.SEARCH_NOT_FOUND.value,
            "recordType": resolved_record_type,
            "searchName": ctx.search_name,
            "availableSearches": cast("JSONValue", available_searches),
            "details": str(original_error),
        }
        raise CoreValidationError(
            title="Search not found",
            detail=f"Search not found: {ctx.search_name}",
            errors=[error_dict],
        ) from original_error

    return response, resolved_record_type
