import time
from dataclasses import dataclass
from typing import Any, cast

from veupath_chatbot.domain.parameters.specs import (
    extract_param_specs,
    unwrap_search_data,
)
from veupath_chatbot.domain.parameters.vocab_utils import flatten_vocab
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    point_uuid,
    sha256_hex,
    stable_json_dumps,
)
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


def _coerce_str(value: object | None) -> str:
    return str(value) if value is not None else ""


def _preview_vocab(vocab: JSONValue, *, limit: int = 50) -> tuple[list[str], bool]:
    if not vocab:
        return [], False
    values: list[str] = []
    seen: set[str] = set()
    truncated = False
    vocab_input: JSONObject | JSONArray
    if isinstance(vocab, (dict, list)):
        vocab_input = vocab
    else:
        return [], False
    for entry in flatten_vocab(vocab_input, prefer_term=False):
        if len(values) >= limit:
            truncated = True
            break
        candidate = entry.get("display") or entry.get("value")
        if not candidate:
            continue
        s = str(candidate)
        if s in seen:
            continue
        seen.add(s)
        values.append(s)
    return values, truncated


def build_record_type_doc(site_id: str, rt: JSONValue) -> JSONObject | None:
    if isinstance(rt, str):
        rt_name = rt
        rt_display = rt
        rt_desc = ""
    elif isinstance(rt, dict):
        rt_name = wdk_entity_name(rt)
        rt_display = str(rt.get("displayName") or rt_name)
        rt_desc = str(rt.get("description") or "")
    else:
        return None

    if not rt_name:
        return None

    return {
        "id": point_uuid(f"{site_id}:{rt_name}"),
        "text": f"{rt_display}\n{rt_name}\n{rt_desc}".strip(),
        "payload": {
            "siteId": site_id,
            "recordType": rt_name,
            "displayName": rt_display,
            "description": rt_desc,
            "displayNamePlural": rt.get("displayNamePlural")
            if isinstance(rt, dict)
            else None,
            "shortDisplayName": rt.get("shortDisplayName")
            if isinstance(rt, dict)
            else None,
            "shortDisplayNamePlural": rt.get("shortDisplayNamePlural")
            if isinstance(rt, dict)
            else None,
            "fullName": rt.get("fullName") if isinstance(rt, dict) else None,
            "urlSegment": rt.get("urlSegment") if isinstance(rt, dict) else rt_name,
            "name": rt.get("name") if isinstance(rt, dict) else rt_name,
            "iconName": rt.get("iconName") if isinstance(rt, dict) else None,
            "recordIdAttributeName": rt.get("recordIdAttributeName")
            if isinstance(rt, dict)
            else None,
            "primaryKeyColumnRefs": rt.get("primaryKeyColumnRefs")
            if isinstance(rt, dict)
            else None,
            "useBasket": rt.get("useBasket") if isinstance(rt, dict) else None,
            "formats": rt.get("formats") if isinstance(rt, dict) else None,
            "attributes": rt.get("attributes") if isinstance(rt, dict) else None,
            "tables": rt.get("tables") if isinstance(rt, dict) else None,
            "source": "wdk",
        },
    }


def _extract_canonical_params(raw_specs: JSONArray) -> JSONArray:
    """Extract canonical parameter dicts from raw WDK param specs.

    Each output dict contains: name, displayName, type, help, isRequired,
    allowEmptyValue, defaultValue, vocabulary, vocabularyPreview, vocabularyTruncated.
    """
    canonical_params: JSONArray = []
    for spec in raw_specs:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name") or spec.get("paramName") or spec.get("id")
        if not name:
            continue
        vocab = spec.get("vocabulary")
        vocab_preview, vocab_truncated = _preview_vocab(vocab, limit=50)
        canonical_params.append(
            {
                "name": str(name),
                "displayName": spec.get("displayName") or str(name),
                "type": spec.get("type") or "string",
                "help": spec.get("help") or "",
                "isRequired": bool(spec.get("isRequired", False))
                if "isRequired" in spec
                else (not bool(spec.get("allowEmptyValue", False))),
                "allowEmptyValue": bool(spec.get("allowEmptyValue", True))
                if "allowEmptyValue" in spec
                else None,
                "defaultValue": spec.get("defaultValue")
                if spec.get("defaultValue") is not None
                else spec.get("initialDisplayValue"),
                "vocabulary": vocab,
                "vocabularyPreview": cast("Any", vocab_preview),
                "vocabularyTruncated": vocab_truncated,
            }
        )
    return canonical_params


def _resolve_display_fields(
    details_unwrapped: JSONObject,
    summary_unwrapped: JSONObject,
    search_name: str,
) -> tuple[str, str, str, str, str]:
    """Resolve display_name, short, description, summary, help from details/summary.

    Falls back through details -> summary -> search_name for display_name.
    Returns (display_name, short, description, summary, help_text).
    """
    display_name = _coerce_str(
        details_unwrapped.get("displayName")
        or summary_unwrapped.get("displayName")
        or summary_unwrapped.get("shortDisplayName")
        or search_name
    )
    short = _coerce_str(
        details_unwrapped.get("shortDisplayName")
        or summary_unwrapped.get("shortDisplayName")
        or ""
    )
    description = _coerce_str(
        details_unwrapped.get("description")
        or summary_unwrapped.get("description")
        or ""
    )
    summary = _coerce_str(details_unwrapped.get("summary") or "")
    help_text = _coerce_str(details_unwrapped.get("help") or "")
    return display_name, short, description, summary, help_text


@dataclass
class SearchPayloadFields:
    """Fields required to assemble a search payload."""

    site_id: str
    rt_name: str
    search_name: str
    display_name: str
    short: str
    description: str
    summary: str
    help_text: str
    canonical_params: JSONArray
    details_unwrapped: JSONObject
    summary_unwrapped: JSONObject
    base_url: str
    is_internal: bool
    details_error: str | None


def _assemble_search_payload(fields: SearchPayloadFields) -> JSONObject:
    """Assemble the search payload dict with source hash."""
    d = fields.details_unwrapped
    s = fields.summary_unwrapped
    payload: JSONObject = {
        "siteId": fields.site_id,
        "recordType": fields.rt_name,
        "searchName": fields.search_name,
        "displayName": fields.display_name,
        "shortDisplayName": fields.short,
        "description": fields.description,
        "summary": fields.summary,
        "help": fields.help_text,
        "isInternal": fields.is_internal,
        "paramSpecs": fields.canonical_params,
        "fullName": d.get("fullName") or s.get("fullName"),
        "urlSegment": d.get("urlSegment") or s.get("urlSegment") or fields.search_name,
        "outputRecordClassName": d.get("outputRecordClassName") or fields.rt_name,
        "paramNames": d.get("paramNames") or s.get("paramNames"),
        "groups": d.get("groups") or s.get("groups"),
        "filters": d.get("filters") or s.get("filters"),
        "defaultAttributes": d.get("defaultAttributes") or s.get("defaultAttributes"),
        "defaultSorting": d.get("defaultSorting") or s.get("defaultSorting"),
        "dynamicAttributes": d.get("dynamicAttributes") or s.get("dynamicAttributes"),
        "defaultSummaryView": d.get("defaultSummaryView")
        or s.get("defaultSummaryView"),
        "noSummaryOnSingleRecord": d.get("noSummaryOnSingleRecord")
        or s.get("noSummaryOnSingleRecord"),
        "summaryViewPlugins": d.get("summaryViewPlugins")
        or s.get("summaryViewPlugins"),
        "allowedPrimaryInputRecordClassNames": d.get(
            "allowedPrimaryInputRecordClassNames"
        ),
        "allowedSecondaryInputRecordClassNames": d.get(
            "allowedSecondaryInputRecordClassNames"
        ),
        "isAnalyzable": d.get("isAnalyzable") or s.get("isAnalyzable"),
        "isCacheable": d.get("isCacheable") or s.get("isCacheable"),
        "isBeta": d.get("isBeta"),
        "queryName": d.get("queryName") or s.get("queryName"),
        "newBuild": d.get("newBuild"),
        "reviseBuild": d.get("reviseBuild"),
        "searchVisibleHelp": d.get("searchVisibleHelp"),
        "sourceUrl": (
            f"{fields.base_url}/record-types/{fields.rt_name}"
            f"/searches/{fields.search_name}"
        ),
        "ingestedAt": int(time.time()),
    }
    if fields.details_error:
        payload["detailsError"] = fields.details_error
    payload["sourceHash"] = sha256_hex(stable_json_dumps(payload))
    return payload


def _build_search_text(
    display_name: str,
    search_name: str,
    rt_name: str,
    summary: str,
    description: str,
    canonical_params: JSONArray,
) -> str:
    """Build the searchable text blob from display fields and params."""
    return "\n".join(
        [
            display_name,
            search_name,
            rt_name,
            summary,
            description,
            " ".join(
                (
                    f"{p.get('name', '')} {p.get('displayName', '')} "
                    f"{p.get('type', '')} {p.get('help', '')}"
                )
                for p in canonical_params
                if isinstance(p, dict)
            ),
        ]
    ).strip()


def _should_skip_search(s: JSONObject) -> bool:
    """Return True if the search dict should be skipped."""
    if not isinstance(s, dict):
        return True
    if s.get("isInternal", False):
        return True
    return not wdk_entity_name(s)


def build_search_doc(
    site_id: str,
    rt_name: str,
    s: JSONObject,
    details_unwrapped: JSONObject,
    details_error: str | None,
    base_url: str,
) -> JSONObject | None:
    if _should_skip_search(s):
        return None
    search_name = wdk_entity_name(s)

    summary_unwrapped = unwrap_search_data(s if isinstance(s, dict) else {}) or {}

    raw_specs = extract_param_specs(details_unwrapped) if details_unwrapped else []
    canonical_params = _extract_canonical_params(raw_specs)

    display_name, short, description, summary, help_text = _resolve_display_fields(
        details_unwrapped, summary_unwrapped, search_name
    )

    payload_fields = SearchPayloadFields(
        site_id=site_id,
        rt_name=rt_name,
        search_name=search_name,
        display_name=display_name,
        short=short,
        description=description,
        summary=summary,
        help_text=help_text,
        canonical_params=canonical_params,
        details_unwrapped=details_unwrapped,
        summary_unwrapped=summary_unwrapped,
        base_url=base_url,
        is_internal=bool(s.get("isInternal", False)),
        details_error=details_error,
    )
    payload = _assemble_search_payload(payload_fields)

    text = _build_search_text(
        display_name, search_name, rt_name, summary, description, canonical_params
    )

    return {
        "id": point_uuid(f"{site_id}:{rt_name}:{search_name}"),
        "text": text,
        "payload": payload,
    }
