"""Search details discovery with fallback scanning.

Handles fetching search details from the WDK discovery service,
including fallback scanning across all record types when the initial
fetch fails.
"""

from difflib import get_close_matches
from typing import Any, cast

from assistant_core.platform.types import JSONObject
from pydantic import JsonValue

from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.discovery_service import get_discovery_service
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearchResponse,
)
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
)
from pathfinder.platform.errors import ValidationError as CoreValidationError


async def fetch_search_details(
    ctx: SearchContext,
    *,
    record_types: list[WDKRecordType] | None = None,
) -> tuple[WDKSearchResponse, str]:
    """Fetch search details, falling back to scanning all record types.

    :param ctx: Search context (site_id + record_type + search_name).
    :param record_types: All available record types (for fallback scan).
    :returns: Tuple of (WDKSearchResponse, resolved record type).
    :raises CoreValidationError: When the search cannot be found.
    """
    discovery = get_discovery_service()
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


def _unreadable_search(
    search_name: str, record_type: str, cause: Exception
) -> CoreValidationError:
    """The search is listed and its definition could not be read."""
    detail = f"reading {search_name} failed: {cause}"
    error_dict: JSONObject = {
        "path": "searchName",
        "message": detail,
        "code": ErrorCode.WDK_ERROR.value,
        "recordType": record_type,
        "searchName": search_name,
    }
    return CoreValidationError(
        title="Search definition could not be read",
        detail=detail,
        errors=[error_dict],
    )


async def _fallback_scan_record_types(
    discovery: Any,
    ctx: SearchContext,
    *,
    record_types: list[WDKRecordType],
    original_error: Exception,
) -> tuple[WDKSearchResponse, str]:
    """Scan all record types trying to find the search, raising if not found."""
    resolved_record_type = ctx.record_type
    for rt in record_types:
        rt_name = rt.url_segment
        if not rt_name:
            continue
        searches = await discovery.get_searches(ctx.site_id, rt_name)
        if any(s.url_segment == ctx.search_name for s in searches):
            rt_ctx = SearchContext(ctx.site_id, rt_name, ctx.search_name)
            try:
                response = await discovery.get_search_details(
                    rt_ctx, expand_params=True
                )
            except AppError as exc:
                raise _unreadable_search(ctx.search_name, rt_name, exc) from exc
            return response, rt_name

    available = await discovery.get_searches(ctx.site_id, resolved_record_type)
    available_searches: list[str] = [s.url_segment for s in available]
    if ctx.search_name in available_searches:
        raise _unreadable_search(
            ctx.search_name, resolved_record_type, original_error
        ) from original_error
    suggestions = [
        name
        for name in get_close_matches(
            ctx.search_name, available_searches, n=5, cutoff=0.3
        )
        if name != ctx.search_name
    ]
    detail = f"Search not found: {ctx.search_name}."
    if suggestions:
        detail += f" Did you mean: {suggestions}?"
    error_dict: JSONObject = {
        "path": "searchName",
        "message": detail,
        "code": ErrorCode.SEARCH_NOT_FOUND.value,
        "recordType": resolved_record_type,
        "searchName": ctx.search_name,
        "availableSearches": cast("JsonValue", available_searches),
        "details": str(original_error),
    }
    raise CoreValidationError(
        title="Search not found",
        detail=detail,
        errors=[error_dict],
    ) from original_error
