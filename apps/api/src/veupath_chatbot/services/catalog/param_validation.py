"""Validation of search parameter values."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

import httpx

from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
    find_missing_required_params,
    unwrap_search_data,
)
from veupath_chatbot.integrations.veupathdb.client import (
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import AppError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

from .param_resolution import (
    _extract_param_names,
    _filter_context_values,
    expand_search_details_with_params,
)

logger = get_logger(__name__)


class _ResolveRecordTypeCallback(Protocol):
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
    """Caller-provided callbacks for parameter validation."""

    resolve_record_type_for_search: _ResolveRecordTypeCallback
    find_record_type_hint: Callable[[str, str | None], Awaitable[str | None]]
    extract_vocab_options: Callable[[JSONObject], list[str]]


# Truncate vocab option lists in validation error responses to keep
# error payloads reasonably sized for the LLM and frontend display.
_MAX_OPTION_EXAMPLES = 50
# Limit known-param-name lists in "unknown parameter" errors so the
# error payload stays readable without dumping every WDK parameter.
_MAX_KNOWN_PARAM_NAMES = 50


async def validate_search_params(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    context_values: JSONObject | None,
) -> JSONObject:
    """Validate and canonicalize search parameters for UI consumption.

    Returns a stable payload:
      { "validation": { "isValid": bool, "normalizedContextValues": {...}, "errors": {...} } }

    The goal is to keep the frontend a consumer of backend normalization + validation,
    without requiring the UI to interpret raw WDK payloads.
    """
    raw_context = context_values or {}
    normalized_context: JSONObject = {}
    details: JSONObject | None = None
    allowed: set[str] = set()

    try:
        details = await expand_search_details_with_params(
            site_id=site_id,
            record_type=record_type,
            search_name=search_name,
            context_values=raw_context,
        )
        allowed = _extract_param_names(details if isinstance(details, dict) else {})
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": {},
                "errors": {
                    "general": [f"Failed to load search metadata: {exc}"],
                    "byKey": {},
                },
            }
        }

    filtered_context = _filter_context_values(raw_context, allowed)
    spec_payload = unwrap_search_data(details) or {}
    spec_map = adapt_param_specs(spec_payload)
    raw_specs = extract_param_specs(spec_payload)

    try:
        canonicalizer = ParameterCanonicalizer(spec_map)
        normalized_context = canonicalizer.canonicalize(filtered_context)
    except ValidationError as exc:
        by_key: dict[str, list[str]] = {}
        general: list[str] = []
        for err_raw in (exc.errors or []) or []:
            if not isinstance(err_raw, dict):
                continue
            param_raw = err_raw.get("param") or err_raw.get("path")
            param = param_raw if isinstance(param_raw, str) else None
            message_raw = err_raw.get("message") or err_raw.get("detail")
            message = (
                message_raw
                if isinstance(message_raw, str)
                else (exc.detail or exc.title)
            )
            if param:
                by_key.setdefault(param, []).append(message)
            else:
                general.append(str(message))
        if not general:
            general = [exc.detail or exc.title]
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": {},
                "errors": {
                    "general": cast("JSONValue", general),
                    "byKey": cast("JSONValue", by_key),
                },
            }
        }

    # Required checks using raw WDK specs (keeps semantics aligned with WDK).
    missing = find_missing_required_params(raw_specs, normalized_context)

    if missing:
        by_key = {name: ["Required"] for name in missing}
        return {
            "validation": {
                "isValid": False,
                "normalizedContextValues": normalized_context,
                "errors": {
                    "general": cast(
                        "JSONValue",
                        [f"Missing required parameters: {', '.join(missing)}"],
                    ),
                    "byKey": cast("JSONValue", by_key),
                },
            }
        }

    return {
        "validation": {
            "isValid": True,
            "normalizedContextValues": normalized_context,
            "errors": {"general": [], "byKey": {}},
        }
    }


async def _resolve_search_details(
    *,
    site_id: str,
    resolved_record_type: str,
    search_name: str,
    record_type: str,
    parameters: JSONObject,
) -> JSONObject:
    """Fetch search details with contextual params, with fallback.

    Raises ``ValidationError`` with available-search hints when the
    search cannot be found at all.
    """
    discovery = get_discovery_service()
    try:
        wdk_client = get_wdk_client(site_id)
        context = encode_context_param_values_for_wdk(parameters)
        try:
            return await wdk_client.get_search_details_with_params(
                resolved_record_type,
                search_name,
                context=context,
                expand_params=True,
            )
        except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Contextual param fetch failed, falling back to non-contextual specs",
                record_type=resolved_record_type,
                search_name=search_name,
                error=str(exc),
            )
            return await discovery.get_search_details(
                site_id, resolved_record_type, search_name, expand_params=True
            )
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
        hint_record_type = await _find_search_record_type_hint(
            discovery, site_id, record_type, search_name
        )
        available = await _collect_available_search_names(
            discovery, site_id, resolved_record_type
        )
        raise ValidationError(
            title=f"Unknown or invalid search: {search_name}",
            detail=str(exc),
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "availableSearches": cast("JSONValue", available),
                        "recordTypeHint": hint_record_type,
                    }
                }
            ],
        ) from exc


async def _collect_available_search_names(
    discovery: object, site_id: str, resolved_record_type: str
) -> list[str]:
    """Collect available search names for a record type (for error context)."""
    searches = await discovery.get_searches(site_id, resolved_record_type)
    available: list[str] = []
    for s in searches:
        if not isinstance(s, dict):
            continue
        name_raw = s.get("name")
        url_seg_raw = s.get("urlSegment")
        name = name_raw if isinstance(name_raw, str) else None
        url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
        available_val = name or url_seg
        if isinstance(available_val, str):
            available.append(available_val)
    return available


async def _find_search_record_type_hint(
    discovery: object, site_id: str, record_type: str, search_name: str
) -> str | None:
    """Search other record types to find where *search_name* actually lives."""
    try:
        record_types = await discovery.get_record_types(site_id)
        for rt in record_types:
            if not isinstance(rt, dict):
                continue
            url_seg_raw = rt.get("urlSegment")
            name_raw = rt.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            rt_name = url_seg or name or ""
            if not rt_name or rt_name == record_type:
                continue
            rt_searches = await discovery.get_searches(site_id, rt_name)
            for s in rt_searches:
                if not isinstance(s, dict):
                    continue
                s_url_seg_raw = s.get("urlSegment")
                s_name_raw = s.get("name")
                s_url_seg = s_url_seg_raw if isinstance(s_url_seg_raw, str) else None
                s_name = s_name_raw if isinstance(s_name_raw, str) else None
                if search_name in (s_url_seg, s_name):
                    return rt_name
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as hint_exc:
        logger.warning(
            "Record type hint resolution failed",
            search_name=search_name,
            error=str(hint_exc),
        )
    return None


def _build_missing_param_options(
    param_specs: list[JSONObject],
    missing: list[str],
    extract_vocab_options: Callable[[JSONObject], list[str]],
) -> JSONObject:
    """Build vocabulary option hints for missing required parameters."""
    options: JSONObject = {}
    for param_spec in param_specs:
        name_raw = param_spec.get("name")
        name = name_raw if isinstance(name_raw, str) else None
        if not name or name not in missing:
            continue
        vocab_raw = param_spec.get("vocabulary")
        opts: list[str] = []
        if isinstance(vocab_raw, dict):
            opts = extract_vocab_options(vocab_raw)
        elif isinstance(vocab_raw, list):
            if vocab_raw and isinstance(vocab_raw[0], list):
                opts = [
                    str(v[0])
                    for v in vocab_raw[:_MAX_OPTION_EXAMPLES]
                    if isinstance(v, list) and v
                ]
            else:
                opts = [str(v) for v in vocab_raw[:_MAX_OPTION_EXAMPLES]]
        if opts:
            options[name] = cast(
                "JSONValue",
                {
                    "examples": cast("JSONValue", opts),
                    "truncated": len(opts) >= _MAX_OPTION_EXAMPLES,
                },
            )
    return options


async def validate_parameters(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
    callbacks: ValidationCallbacks,
) -> None:
    """Validate parameters against WDK search specs.

    Normalizes *parameters* in-place and raises ``ValidationError`` when
    the search is unknown, extra/unknown parameters are provided, or
    required parameters are missing.
    """
    resolved_record_type = await callbacks.resolve_record_type_for_search(
        record_type, search_name, require_match=True, allow_fallback=True
    )
    if resolved_record_type is None:
        record_type_hint = await callbacks.find_record_type_hint(
            search_name, record_type
        )
        raise ValidationError(
            title=f"Unknown or invalid search: {search_name}",
            detail="Search name not found in any record type.",
            errors=[
                {
                    "context": {
                        "recordType": record_type,
                        "recordTypeHint": record_type_hint,
                    }
                }
            ],
        )

    details = await _resolve_search_details(
        site_id=site_id,
        resolved_record_type=resolved_record_type,
        search_name=search_name,
        record_type=record_type,
        parameters=parameters,
    )

    spec_payload = unwrap_search_data(details) or {}
    param_specs = extract_param_specs(spec_payload)
    param_spec_map = adapt_param_specs(spec_payload)
    normalizer = ParameterNormalizer(param_spec_map)
    normalized = normalizer.normalize(parameters)
    parameters.clear()
    parameters.update(normalized)
    param_names: set[str] = set()
    for p in param_specs:
        if not isinstance(p, dict):
            continue
        name_raw = p.get("name")
        if isinstance(name_raw, str):
            param_names.add(name_raw)
    extra_params = [key for key in parameters if key not in param_names]
    if extra_params:
        raise ValidationError(
            title="Unknown parameters provided",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "unknown": cast("JSONValue", extra_params),
                        "known": cast(
                            "JSONValue", sorted(param_names)[:_MAX_KNOWN_PARAM_NAMES]
                        ),
                        "truncated": len(param_names) > _MAX_KNOWN_PARAM_NAMES,
                    }
                }
            ],
        )
    missing = find_missing_required_params(param_specs, parameters)

    if missing:
        valid_specs = [p for p in param_specs if isinstance(p, dict)]
        options = _build_missing_param_options(
            valid_specs, missing, callbacks.extract_vocab_options
        )
        raise ValidationError(
            title="Missing required parameters",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "missing": cast("JSONValue", missing),
                        "options": options,
                    }
                }
            ],
        )
