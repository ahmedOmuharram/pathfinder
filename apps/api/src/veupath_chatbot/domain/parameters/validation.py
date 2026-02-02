"""Parameter validation logic (WDK-backed)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs, extract_param_specs
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service


async def validate_parameters(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: dict[str, Any],
    resolve_record_type_for_search: Callable[
        [str | None, str | None, bool, bool], Awaitable[str | None]
    ],
    find_record_type_hint: Callable[[str, str | None], Awaitable[str | None]],
    extract_vocab_options: Callable[[dict[str, Any]], list[str]],
) -> None:
    discovery = get_discovery_service()
    resolved_record_type = await resolve_record_type_for_search(
        record_type, search_name, True, False
    )
    if resolved_record_type is None:
        record_type_hint = await find_record_type_hint(search_name, exclude=record_type)
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
        details = await discovery.get_search_details(
            site_id, resolved_record_type, search_name, expand_params=True
        )
    except Exception as exc:
        searches = await discovery.get_searches(site_id, resolved_record_type)
        available = [s.get("name") or s.get("urlSegment") for s in searches]
        record_type_hint = None
        try:
            record_types = await discovery.get_record_types(site_id)
            for rt in record_types:
                rt_name = rt.get("urlSegment", rt.get("name", ""))
                if not rt_name or rt_name == record_type:
                    continue
                rt_searches = await discovery.get_searches(site_id, rt_name)
                match = next(
                    (
                        s
                        for s in rt_searches
                        if s.get("urlSegment") == search_name
                        or s.get("name") == search_name
                    ),
                    None,
                )
                if match:
                    record_type_hint = rt_name
                    break
        except Exception:
            record_type_hint = None
        raise ValidationError(
            title=f"Unknown or invalid search: {search_name}",
            detail=str(exc),
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "availableSearches": [s for s in available if s],
                        "recordTypeHint": record_type_hint,
                    }
                }
            ],
        ) from exc

    if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
        details = details["searchData"]

    spec_payload = details if isinstance(details, dict) else {}
    param_specs = extract_param_specs(spec_payload)
    param_spec_map = adapt_param_specs(spec_payload)
    normalizer = ParameterNormalizer(param_spec_map)
    try:
        normalized = normalizer.normalize(parameters)
    except ValidationError as exc:
        raise exc
    parameters.clear()
    parameters.update(normalized)
    param_names = {p.get("name") for p in param_specs if p.get("name") is not None}
    extra_params = [key for key in parameters.keys() if key not in param_names]
    if extra_params:
        raise ValidationError(
            title="Unknown parameters provided",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "unknown": extra_params,
                        "known": sorted(param_names)[:50],
                        "truncated": len(param_names) > 50,
                    }
                }
            ],
        )
    required_params = [
        p
        for p in param_specs
        if p.get("isRequired", False) or not p.get("allowEmptyValue", True)
    ]
    missing: list[str] = []
    for param in required_params:
        name = param.get("name")
        if not name:
            continue
        if name not in parameters:
            missing.append(name)
            continue
        value = parameters.get(name)
        param_type = param.get("type", "")
        if param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]"):
                missing.append(name)
            continue
        if value in (None, "", [], {}):
            missing.append(name)

    if missing:
        options: dict[str, Any] = {}
        for param in param_specs:
            name = param.get("name")
            if name in missing:
                vocab = param.get("vocabulary")
                opts: list[str] = []
                if isinstance(vocab, dict):
                    opts = extract_vocab_options(vocab)
                elif isinstance(vocab, list):
                    if vocab and isinstance(vocab[0], list):
                        opts = [str(v[0]) for v in vocab[:50]]
                    else:
                        opts = [str(v) for v in vocab[:50]]
                if opts:
                    options[name] = {
                        "examples": opts,
                        "truncated": len(opts) >= 50,
                    }

        raise ValidationError(
            title="Missing required parameters",
            errors=[
                {
                    "context": {
                        "recordType": resolved_record_type,
                        "searchName": search_name,
                        "missing": missing,
                        "options": options,
                    }
                }
            ],
        )

    return None

