"""Validation of search parameter values."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pathfinder.domain.parameters.canonicalize import ParameterCanonicalizer
from pathfinder.domain.parameters.specs import find_missing_required_params
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.discovery_service import (
    DiscoveryService,
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearchResponse,
    encode_wdk_params,
)
from pathfinder.platform.errors import AppError, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search

from .param_formatting import format_param_info_typed
from .param_resolution import (
    _extract_param_names_from_response,
    _filter_context_values,
    expand_search_details_with_params,
)

logger = get_logger(__name__)

class _ValidationErrorEntry(BaseModel):
    """Single error entry from WDK validation responses."""

    model_config = ConfigDict(extra="ignore")
    param: str | None = None
    path: str | None = None
    message: str | None = None
    detail: str | None = None

class ValidationErrors(CamelModel):
    """Structured validation errors by category."""

    general: list[str] = Field(default_factory=list)
    by_key: dict[str, list[str]] = Field(default_factory=dict)

class ValidationResult(CamelModel):
    """Single validation result with normalized values."""

    is_valid: bool
    normalized_context_values: JSONObject = Field(default_factory=dict)
    errors: ValidationErrors = Field(default_factory=ValidationErrors)

class ValidationResponse(CamelModel):
    """Top-level validation response wrapper."""

    validation: ValidationResult

class ResolveRecordTypeFn(Protocol):
    """Protocol for resolve_record_type_for_search callbacks."""

    async def __call__(
        self,
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = ...,
        allow_fallback: bool = ...,
    ) -> str | None: ...

@dataclass(frozen=True)
class ValidationCallbacks:
    """Caller-provided callbacks for parameter validation.

    ``validation_error_payload`` is optional — only needed when the caller
    wants to convert :class:`ValidationError` into a ``tool_error`` payload
    (e.g. during step creation).
    """

    resolve_record_type_for_search: ResolveRecordTypeFn
    find_record_type_hint: Callable[[str, str | None], Awaitable[str | None]]
    validation_error_payload: Callable[[ValidationError], ToolErrorPayload] | None = None

async def validate_search_params(
    ctx: SearchContext,
    *,
    context_values: JSONObject | None,
) -> ValidationResponse:
    """Validate and canonicalize search parameters for UI consumption.

    Returns a stable payload:
      { "validation": { "isValid": bool, "normalizedContextValues": {...}, "errors": {...} } }

    The goal is to keep the frontend a consumer of backend normalization + validation,
    without requiring the UI to interpret raw WDK payloads.
    """
    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    response: WDKSearchResponse | None = None
    allowed: set[str] = set()

    try:
        response = await expand_search_details_with_params(ctx, raw_context)
        allowed = _extract_param_names_from_response(response)
    except AppError as exc:
        return ValidationResponse(
            validation=ValidationResult(
                is_valid=False,
                errors=ValidationErrors(
                    general=[f"Failed to load search metadata: {exc}"]
                ),
            )
        )

    filtered_context = _filter_context_values(raw_context, allowed)
    spec_map = adapt_param_specs_from_search(response.search_data)

    try:
        canonicalizer = ParameterCanonicalizer(spec_map)
        normalized_context = canonicalizer.canonicalize(filtered_context)
    except ValidationError as exc:
        by_key: dict[str, list[str]] = {}
        general: list[str] = []
        for err_raw in exc.errors or []:
            if not isinstance(err_raw, dict):
                continue
            entry = _ValidationErrorEntry.model_validate(err_raw)
            param_name = entry.param or entry.path
            message = entry.message or entry.detail or exc.detail or exc.title
            if param_name:
                by_key.setdefault(param_name, []).append(message)
            else:
                general.append(str(message))
        if not general:
            general = [exc.detail or exc.title]
        return ValidationResponse(
            validation=ValidationResult(
                is_valid=False,
                errors=ValidationErrors(general=general, by_key=by_key),
            )
        )

    # Required checks using raw WDK specs (keeps semantics aligned with WDK).
    missing = find_missing_required_params(spec_map, normalized_context)

    if missing:
        by_key = {name: ["Required"] for name in missing}
        return ValidationResponse(
            validation=ValidationResult(
                is_valid=False,
                normalized_context_values=normalized_context,
                errors=ValidationErrors(
                    general=[f"Missing required parameters: {', '.join(missing)}"],
                    by_key=by_key,
                ),
            )
        )

    return ValidationResponse(
        validation=ValidationResult(
            is_valid=True,
            normalized_context_values=normalized_context,
        )
    )

async def _resolve_search_details(
    ctx: SearchContext,
    *,
    resolved_record_type: str,
    parameters: JSONObject,
) -> WDKSearchResponse:
    """Fetch search details with contextual params, with fallback.

    ``ctx`` carries the original (site_id, record_type, search_name) for
    error-hint generation; ``resolved_record_type`` is the already-resolved
    record type used for the actual WDK call.

    Raises ``ValidationError`` with available-search hints when the
    search cannot be found at all.
    """
    discovery = get_discovery_service()
    try:
        wdk_client = get_wdk_client(ctx.site_id)
        context = encode_wdk_params(parameters)
        try:
            return await wdk_client.get_search_details_with_params(
                resolved_record_type,
                ctx.search_name,
                context=context,
                expand_params=True,
            )
        except AppError as exc:
            logger.warning(
                "Contextual param fetch failed, falling back to non-contextual specs",
                record_type=resolved_record_type,
                search_name=ctx.search_name,
                error=str(exc),
            )
            resolved_ctx = SearchContext(
                ctx.site_id, resolved_record_type, ctx.search_name
            )
            return await discovery.get_search_details(resolved_ctx, expand_params=True)
    except AppError as exc:
        hint_record_type = await _find_search_record_type_hint(discovery, ctx)
        available = await _collect_available_search_names(
            discovery, ctx.site_id, resolved_record_type
        )
        raise ValidationError(
            title=f"Unknown or invalid search: {ctx.search_name}",
            detail=str(exc),
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "availableSearches": cast("JsonValue", available),
                        "recordTypeHint": hint_record_type,
                    }
                }
            ],
        ) from exc

async def _collect_available_search_names(
    discovery: DiscoveryService, site_id: str, resolved_record_type: str
) -> list[str]:
    """Collect available search names for a record type (for error context)."""
    searches = await discovery.get_searches(site_id, resolved_record_type)
    return [s.url_segment for s in searches]

async def _find_search_record_type_hint(
    discovery: DiscoveryService, ctx: SearchContext
) -> str | None:
    """Search other record types to find where *search_name* actually lives."""
    try:
        record_types = await discovery.get_record_types(ctx.site_id)
        for rt in record_types:
            rt_name = rt.url_segment
            if not rt_name or rt_name == ctx.record_type:
                continue
            rt_searches = await discovery.get_searches(ctx.site_id, rt_name)
            for s in rt_searches:
                if ctx.search_name == s.url_segment:
                    return rt_name
    except AppError as hint_exc:
        logger.warning(
            "Record type hint resolution failed",
            search_name=ctx.search_name,
            error=str(hint_exc),
        )
    return None

async def validate_parameters(
    ctx: SearchContext,
    *,
    parameters: JSONObject,
    callbacks: ValidationCallbacks,
) -> JSONObject:
    """Validate parameters against WDK search specs.

    Returns the **canonicalized** parameters as a new dict (decoded form:
    multi-pick → ``list[str]``, single-pick → ``str``, ranges → dict).
    Does NOT mutate *parameters*. Raises ``ValidationError`` when the
    search is unknown, extra/unknown parameters are provided, or required
    parameters are missing.
    """
    resolved_record_type = await callbacks.resolve_record_type_for_search(
        ctx.record_type, ctx.search_name, require_match=True, allow_fallback=True
    )
    if resolved_record_type is None:
        record_type_hint = await callbacks.find_record_type_hint(
            ctx.search_name, ctx.record_type
        )
        raise ValidationError(
            title=f"Unknown or invalid search: {ctx.search_name}",
            detail="Search name not found in any record type.",
            errors=[
                {
                    "context": {
                        "recordType": ctx.record_type,
                        "recordTypeHint": record_type_hint,
                    }
                }
            ],
        )

    response = await _resolve_search_details(
        ctx,
        resolved_record_type=resolved_record_type,
        parameters=parameters,
    )

    param_spec_map = adapt_param_specs_from_search(response.search_data)
    canonicalizer = ParameterCanonicalizer(param_spec_map)
    canonical: JSONObject = canonicalizer.canonicalize(parameters)
    param_names = _extract_param_names_from_response(response)
    extra_params = [key for key in canonical if key not in param_names]
    if extra_params:
        full_param_spec = format_param_info_typed(response.search_data.parameters or [])
        serialized_spec: JsonValue = [
            p.model_dump(by_alias=True, mode="json", exclude_none=True)
            for p in full_param_spec
        ]
        raise ValidationError(
            title="Unknown parameters provided",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": ctx.search_name,
                        "unknown": cast("JsonValue", extra_params),
                        "parameters": serialized_spec,
                    }
                }
            ],
        )
    missing = find_missing_required_params(param_spec_map, canonical)

    if missing:
        full_param_spec = format_param_info_typed(response.search_data.parameters or [])
        serialized_spec = [
            p.model_dump(by_alias=True, mode="json", exclude_none=True)
            for p in full_param_spec
        ]
        raise ValidationError(
            title=f"Missing required parameters: {', '.join(missing)}",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": ctx.search_name,
                        "missing": cast("JsonValue", missing),
                        "parameters": serialized_spec,
                    }
                }
            ],
        )
    return canonical
