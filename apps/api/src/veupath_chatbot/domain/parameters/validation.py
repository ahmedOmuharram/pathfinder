"""Parameter validation logic (WDK-backed)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
)
from veupath_chatbot.integrations.veupathdb.client import (
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue


async def validate_parameters(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
    resolve_record_type_for_search: Callable[
        [str | None, str | None, bool, bool], Awaitable[str | None]
    ],
    find_record_type_hint: Callable[[str, str | None], Awaitable[str | None]],
    extract_vocab_options: Callable[[JSONObject], list[str]],
) -> None:
    discovery = get_discovery_service()
    resolved_record_type = await resolve_record_type_for_search(
        record_type, search_name, True, True
    )
    if resolved_record_type is None:
        record_type_hint = await find_record_type_hint(search_name, record_type)
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
    try:
        # Many WDK param vocabularies are context-dependent. Prefer the POST variant
        # that accepts `contextParamValues`, so values like "maximum2" validate when
        # the chosen sample sets require them.
        wdk_client = get_wdk_client(site_id)
        context = encode_context_param_values_for_wdk(parameters)
        try:
            details = await wdk_client.get_search_details_with_params(
                resolved_record_type,
                search_name,
                context=context,
                expand_params=True,
            )
        except Exception:
            # Fallback: non-contextual specs (may be incomplete for dependent params).
            details = await discovery.get_search_details(
                site_id, resolved_record_type, search_name, expand_params=True
            )
    except Exception as exc:
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
        hint_record_type: str | None = None
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
                match: JSONObject | None = None
                for s in rt_searches:
                    if not isinstance(s, dict):
                        continue
                    s_url_seg_raw = s.get("urlSegment")
                    s_name_raw = s.get("name")
                    s_url_seg = (
                        s_url_seg_raw if isinstance(s_url_seg_raw, str) else None
                    )
                    s_name = s_name_raw if isinstance(s_name_raw, str) else None
                    if s_url_seg == search_name or s_name == search_name:
                        match = s
                        break
                if match:
                    hint_record_type = rt_name
                    break
        except Exception:
            hint_record_type = None
        raise ValidationError(
            title=f"Unknown or invalid search: {search_name}",
            detail=str(exc),
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "availableSearches": cast(JSONValue, available),
                        "recordTypeHint": hint_record_type,
                    }
                }
            ],
        ) from exc

    details_dict: JSONObject
    if isinstance(details, dict):
        search_data_raw = details.get("searchData")
        details_dict = search_data_raw if isinstance(search_data_raw, dict) else details
    else:
        details_dict = {}

    spec_payload = details_dict
    param_specs = extract_param_specs(spec_payload)
    param_spec_map = adapt_param_specs(spec_payload)
    normalizer = ParameterNormalizer(param_spec_map)
    try:
        normalized = normalizer.normalize(parameters)
    except ValidationError as exc:
        raise exc
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
                        "unknown": cast(JSONValue, extra_params),
                        "known": cast(JSONValue, sorted(param_names)[:50]),
                        "truncated": len(param_names) > 50,
                    }
                }
            ],
        )
    required_params: list[JSONObject] = []
    for p in param_specs:
        if not isinstance(p, dict):
            continue
        is_required_raw = p.get("isRequired")
        allow_empty_raw = p.get("allowEmptyValue")
        is_required = (
            bool(is_required_raw) if isinstance(is_required_raw, bool) else False
        )
        allow_empty = (
            bool(allow_empty_raw) if isinstance(allow_empty_raw, bool) else True
        )
        if is_required or not allow_empty:
            required_params.append(p)
    missing: list[str] = []
    for param in required_params:
        if not isinstance(param, dict):
            continue
        name_raw = param.get("name")
        name = name_raw if isinstance(name_raw, str) else None
        if not name:
            continue
        if name not in parameters:
            missing.append(name)
            continue
        value = parameters.get(name)
        type_raw = param.get("type")
        param_type = type_raw if isinstance(type_raw, str) else ""
        if param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]"):
                missing.append(name)
            continue
        if value in (None, "", [], {}):
            missing.append(name)

    if missing:
        options: JSONObject = {}
        for param_spec in param_specs:
            if not isinstance(param_spec, dict):
                continue
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
                        str(v[0]) for v in vocab_raw[:50] if isinstance(v, list) and v
                    ]
                else:
                    opts = [str(v) for v in vocab_raw[:50]]
            if opts:
                options[name] = cast(
                    JSONValue,
                    {
                        "examples": cast(JSONValue, opts),
                        "truncated": len(opts) >= 50,
                    },
                )

        raise ValidationError(
            title="Missing required parameters",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "missing": cast(JSONValue, missing),
                        "options": options,
                    }
                }
            ],
        )

    return None
