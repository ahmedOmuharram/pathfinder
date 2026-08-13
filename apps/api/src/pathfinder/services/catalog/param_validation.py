"""Validation of search parameter values."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pathfinder.domain.parameters.canonicalize import ParameterCanonicalizer
from pathfinder.domain.parameters.specs import (
    ParamSpecNormalized,
    fill_hidden_required_defaults,
    find_dependent_value_violations,
    find_missing_required_params,
    topological_fill_order,
)
from pathfinder.domain.parameters.values import (
    ParamValue,
    to_decoded_map,
)
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
from pathfinder.services.catalog.param_adapters import (
    adapt_param_from_wdk,
    adapt_param_specs_from_search,
)
from pathfinder.services.catalog.wdk_substitution import substituted_params

from .param_formatting import format_normalized_param_info
from .param_resolution import (
    _extract_param_names_from_response,
    _filter_context_values,
    expand_search_details_with_params,
    get_refreshed_dependent_params,
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

    Set the payload callback only when the caller must turn a validation error
    into a tool error payload.
    """

    resolve_record_type_for_search: ResolveRecordTypeFn
    find_record_type_hint: Callable[[str, str | None], Awaitable[str | None]]
    validation_error_payload: Callable[[ValidationError], ToolErrorPayload] | None = (
        None
    )


async def validate_search_params(
    ctx: SearchContext,
    *,
    context_values: dict[str, ParamValue] | None,
) -> ValidationResponse:
    """Validate and canonicalize search parameters for the UI.

    The frontend consumes this result. It never interprets raw WDK payloads.
    """
    raw_context: dict[str, ParamValue] = context_values or {}
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

    decoded_normalized = to_decoded_map(normalized_context)

    # Required checks using raw WDK specs (keeps semantics aligned with WDK).
    missing = find_missing_required_params(spec_map, decoded_normalized)

    if missing:
        by_key = {name: ["Required"] for name in missing}
        return ValidationResponse(
            validation=ValidationResult(
                is_valid=False,
                normalized_context_values=decoded_normalized,
                errors=ValidationErrors(
                    general=[f"Missing required parameters: {', '.join(missing)}"],
                    by_key=by_key,
                ),
            )
        )

    return ValidationResponse(
        validation=ValidationResult(
            is_valid=True,
            normalized_context_values=decoded_normalized,
        )
    )


async def _resolve_search_details(
    ctx: SearchContext,
    *,
    resolved_record_type: str,
    parameters: dict[str, ParamValue],
) -> WDKSearchResponse:
    """Fetch search details with contextual params, or fall back to static specs.

    The context keeps the original identifiers for error hints. Raises a
    validation error with search hints when WDK does not know the search.
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


class ValidatedParams(CamelModel):
    """Canonical values, and the names WDK supplied rather than accepted."""

    params: dict[str, ParamValue] = Field(default_factory=dict)
    substituted: list[str] = Field(default_factory=list)


async def validate_parameters(
    ctx: SearchContext,
    *,
    parameters: dict[str, ParamValue],
    callbacks: ValidationCallbacks,
) -> ValidatedParams:
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

    # WDK validated these values while answering. Its verdict is authoritative,
    # so it is read before the local checks rather than recomputed after them.
    if response.validation.rejects():
        raise ValidationError(
            title="Invalid parameter value",
            detail="; ".join(response.validation.messages())
            or "WDK rejected these parameter values.",
            errors=[
                {"param": key, "messages": list(texts)}
                for key, texts in (
                    response.validation.errors.by_key
                    if response.validation.errors
                    else {}
                ).items()
            ],
        )

    param_spec_map = adapt_param_specs_from_search(response.search_data)
    canonicalizer = ParameterCanonicalizer(param_spec_map)
    canonical: dict[str, ParamValue] = canonicalizer.canonicalize(parameters)
    refreshed_ctx = SearchContext(
        site_id=ctx.site_id,
        record_type=resolved_record_type,
        search_name=ctx.search_name,
    )
    # The refresh below skips a parent whose value is empty, so hidden required
    # parents must get their defaults first.
    canonical = fill_hidden_required_defaults(param_spec_map, canonical)
    param_spec_map = await _refresh_dependent_vocabularies(
        ctx=refreshed_ctx,
        param_spec_map=param_spec_map,
        canonical_values=canonical,
    )
    canonicalizer = ParameterCanonicalizer(param_spec_map)
    canonical = canonicalizer.canonicalize(parameters)
    canonical = fill_hidden_required_defaults(param_spec_map, canonical)
    param_names = _extract_param_names_from_response(response)
    extra_params = [key for key in canonical if key not in param_names]
    if extra_params:
        full_param_spec = format_normalized_param_info(param_spec_map)
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
    decoded_canonical = to_decoded_map(canonical)
    invalid_dependents = find_dependent_value_violations(
        param_spec_map,
        decoded_canonical,
    )
    if invalid_dependents:
        full_param_spec = format_normalized_param_info(param_spec_map)
        serialized_spec = [
            p.model_dump(by_alias=True, mode="json", exclude_none=True)
            for p in full_param_spec
        ]
        spec_by_name = {p.name: p for p in full_param_spec}
        details = ", ".join(f"{name}={bad}" for name, bad in invalid_dependents)
        invalid_dependents_payload: list[JSONObject] = []
        for name, bad in invalid_dependents:
            entry: JSONObject = {"name": name, "values": cast("JsonValue", bad)}
            spec = spec_by_name.get(name)
            if spec is not None and spec.allowed_values is not None:
                entry["validOptions"] = cast(
                    "JsonValue",
                    [
                        v.model_dump(by_alias=True, mode="json")
                        for v in spec.allowed_values
                    ],
                )
            invalid_dependents_payload.append(entry)
        raise ValidationError(
            title=(
                f"Invalid dependent-parameter values: {details}. "
                "Use the values from the validOptions list for each invalid "
                "dependent parameter — these are the post-refresh vocabulary "
                "for the parent's current value."
            ),
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": ctx.search_name,
                        "invalidDependents": cast(
                            "JsonValue",
                            invalid_dependents_payload,
                        ),
                        "parameters": serialized_spec,
                    },
                },
            ],
        )

    missing = find_missing_required_params(param_spec_map, to_decoded_map(canonical))

    if missing:
        full_param_spec = format_normalized_param_info(param_spec_map)
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
    echoed = {
        spec.name: spec.initial_display_value
        for spec in response.search_data.parameters or []
        if spec.initial_display_value is not None
    }
    return ValidatedParams(
        params=canonical,
        substituted=substituted_params(sent=parameters, echoed=echoed),
    )


async def _refresh_dependent_vocabularies(
    *,
    ctx: SearchContext,
    param_spec_map: dict[str, ParamSpecNormalized],
    canonical_values: dict[str, ParamValue],
) -> dict[str, ParamSpecNormalized]:
    """Refresh each dependent vocabulary against its parent's canonical value.

    A parent with an empty value keeps the static child vocabulary. A failed
    refresh also keeps the static vocabulary.
    """
    next_specs = dict(param_spec_map)
    fill_order = topological_fill_order(next_specs)
    decoded_values = to_decoded_map(canonical_values)
    for parent_name in fill_order:
        parent = next_specs.get(parent_name)
        if parent is None or not parent.dependent_params:
            continue
        parent_value = decoded_values.get(parent_name)
        if parent_value in (None, "", [], {}):
            continue
        try:
            refreshed = await get_refreshed_dependent_params(
                ctx,
                parameter_name=parent_name,
                context_values=canonical_values,
            )
        except AppError as exc:
            logger.warning(
                "refreshed-dependent-params failed; falling back to static vocab",
                parent=parent_name,
                search=ctx.search_name,
                error=str(exc),
            )
            continue
        for refreshed_param in refreshed:
            if refreshed_param.name in parent.dependent_params:
                next_specs[refreshed_param.name] = adapt_param_from_wdk(refreshed_param)
    return next_specs
