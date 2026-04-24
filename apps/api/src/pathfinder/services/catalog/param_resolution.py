"""WDK parameter fetching, caching, and expansion."""

from pathfinder.domain.parameters.canonicalize import ParameterCanonicalizer
from pathfinder.domain.parameters.specs import find_input_step_param
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.client import (
    VEuPathDBClient,
)
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearchResponse,
    encode_wdk_params,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.errors import AppError, ErrorCode, WDKError
from pathfinder.platform.errors import ValidationError as CoreValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search
from pathfinder.services.catalog.param_discovery import fetch_search_details
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.wdk.record_types import resolve_record_type

from .searches import find_record_type_for_search

logger = get_logger(__name__)


class SearchParametersResult(CamelModel):
    """Result of resolving search parameters for a given search."""

    search_name: str
    display_name: str
    description: str | None
    parameters: list[ParameterInfo]
    resolved_record_type: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_search_parameters(ctx: SearchContext) -> SearchParametersResult:
    """Get detailed parameter info for a specific search.

    This is intentionally defensive: WDK responses can vary by site/endpoint.
    """
    discovery = get_discovery_service()
    resolved_record_type = ctx.record_type

    record_types = await discovery.get_record_types(ctx.site_id)

    if ctx.record_type:
        resolved = resolve_record_type(record_types, ctx.record_type)
        if resolved:
            resolved_record_type = resolved

    resolved_ctx = SearchContext(ctx.site_id, resolved_record_type, ctx.search_name)
    response, resolved_record_type = await fetch_search_details(
        discovery,
        resolved_ctx,
        record_types=record_types,
    )

    param_info = format_param_info_typed(response.search_data.parameters or [])

    return SearchParametersResult(
        search_name=ctx.search_name,
        display_name=response.search_data.display_name or ctx.search_name,
        description=response.search_data.description,
        parameters=param_info,
        resolved_record_type=resolved_record_type,
    )


async def get_search_parameters_tool(ctx: SearchContext) -> SearchParametersResult | ToolErrorPayload:
    """Tool-friendly wrapper that returns standardized tool_error payloads."""
    try:
        return await get_search_parameters(ctx)
    except CoreValidationError as exc:
        code = None
        if exc.errors and isinstance(exc.errors, list) and exc.errors:
            first_error = exc.errors[0]
            if isinstance(first_error, dict):
                code_raw = first_error.get("code")
                if isinstance(code_raw, str):
                    code = code_raw
        return tool_error(
            code or ErrorCode.VALIDATION_ERROR,
            exc.detail or exc.title,
            errors=exc.errors,
        )


async def expand_search_details_with_params(
    ctx: SearchContext,
    context_values: JSONObject | None,
) -> WDKSearchResponse:
    """Return WDK search details after applying (WDK-wire) context values.

    NOTE: despite the historical name, this is *not* a pure validation API; it returns
    WDK search details payload. Keep it separate from the public validation endpoint.
    """
    client = get_wdk_client(ctx.site_id)
    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    response, allowed = await _load_discovery_details_and_allowed(ctx)
    filtered_context = _filter_context_values(raw_context, allowed)

    specs = adapt_param_specs_from_search(response.search_data) if response else {}

    if specs:
        canonicalizer = ParameterCanonicalizer(specs)
        try:
            normalized_context = canonicalizer.canonicalize(filtered_context)
        except CoreValidationError:
            resolved_record_type = await find_record_type_for_search(ctx)
            fallback_response = await client.get_search_details_with_params(
                resolved_record_type,
                ctx.search_name,
                encode_wdk_params(filtered_context),
                expand_params=True,
            )
            specs = adapt_param_specs_from_search(fallback_response.search_data)
            canonicalizer = ParameterCanonicalizer(specs)
            normalized_context = canonicalizer.canonicalize(filtered_context)
        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized_context[input_step_param] = ""
    else:
        normalized_context = filtered_context
    resolved_record_type = await find_record_type_for_search(ctx)
    return await _get_search_details_with_portal_fallback(
        site_id=ctx.site_id,
        client=client,
        record_type=resolved_record_type,
        search_name=ctx.search_name,
        context_values=encode_wdk_params(normalized_context),
    )


def _filter_context_values(raw_context: JSONObject, allowed: set[str]) -> JSONObject:
    """Filter context values to keys WDK recognizes for the search (best-effort).

    :param raw_context: Raw context from request.
    :param allowed: Set of allowed parameter names.
    :returns: Filtered context dict.
    """
    return (
        {key: value for key, value in raw_context.items() if key in allowed}
        if allowed
        else dict(raw_context)
    )


async def _load_discovery_details_and_allowed(
    ctx: SearchContext,
) -> tuple[WDKSearchResponse | None, set[str]]:
    """Load discovery search details + extract allowed param names (best-effort)."""
    try:
        discovery = get_discovery_service()
        response = await discovery.get_search_details(ctx, expand_params=True)
        return response, _extract_param_names_from_response(response)
    except AppError as exc:
        logger.warning(
            "Failed to load discovery details for param resolution",
            site_id=ctx.site_id,
            record_type=ctx.record_type,
            search_name=ctx.search_name,
            error=str(exc),
        )
        return None, set()


async def _get_search_details_with_portal_fallback(
    *,
    site_id: str,
    client: VEuPathDBClient,
    record_type: str,
    search_name: str,
    context_values: dict[str, str],
) -> WDKSearchResponse:
    """Call WDK contextual search details, falling back to portal when appropriate."""
    try:
        return await client.get_search_details_with_params(
            record_type,
            search_name,
            context_values,
        )
    except WDKError:
        if site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_search_details_with_params(
                record_type,
                search_name,
                context_values,
            )
        raise


async def get_refreshed_dependent_params(
    ctx: SearchContext,
    *,
    parameter_name: str,
    context_values: JSONObject,
) -> list[WDKParameter]:
    """Get refreshed dependent parameter vocabulary, falling back to the portal.

    Tries the site-specific WDK client first.  If that fails with a
    ``WDKError`` and the site is not already ``veupathdb``, retries against
    the portal client (``veupathdb``).
    """
    encoded = encode_wdk_params(context_values)
    client = get_wdk_client(ctx.site_id)
    try:
        return await client.get_refreshed_dependent_params(
            ctx.record_type,
            ctx.search_name,
            parameter_name,
            encoded,
        )
    except WDKError:
        if ctx.site_id != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_refreshed_dependent_params(
                ctx.record_type,
                ctx.search_name,
                parameter_name,
                encoded,
            )
        raise


def _extract_param_names_from_response(response: WDKSearchResponse) -> set[str]:
    """Extract parameter names from a typed WDKSearchResponse.

    Uses ``param_names`` (always present) from the search data.
    Falls back to ``parameters`` list if param_names is empty.
    """
    search = response.search_data
    if search.param_names:
        return set(search.param_names)
    if search.parameters:
        return {p.name for p in search.parameters}
    return set()
