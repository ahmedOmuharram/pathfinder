"""Search listing and searching functions."""

from __future__ import annotations

import logging
import re

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.site_search import (
    query_site_search,
    strip_html_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONValue

logger = logging.getLogger(__name__)


async def list_searches(site_id: str, record_type: str) -> list[dict[str, str]]:
    """List searches for a specific record type."""
    discovery = get_discovery_service()
    searches = await discovery.get_searches(site_id, record_type)
    result: list[dict[str, str]] = []
    for s in searches:
        if not isinstance(s, dict):
            continue
        is_internal_raw = s.get("isInternal")
        if isinstance(is_internal_raw, bool) and is_internal_raw:
            continue
        url_segment_raw = s.get("urlSegment")
        name_raw = s.get("name")
        url_segment = url_segment_raw if isinstance(url_segment_raw, str) else None
        name = name_raw if isinstance(name_raw, str) else ""
        display_name_raw = s.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else ""
        description_raw = s.get("description")
        description = description_raw if isinstance(description_raw, str) else ""
        result.append(
            {
                "name": url_segment or name,
                "displayName": display_name,
                "description": description,
            }
        )
    return result


async def _search_for_searches_via_site_search(
    site_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, str]]:
    """Search WDK searches via the site's /site-search service.

    This mirrors the webapp search UI (`/app/search`) when filtering to
    documentType=search.
    """
    try:
        data = await query_site_search(
            site_id,
            search_text=query,
            document_type="search",
            limit=limit,
            offset=0,
        )
    except Exception as exc:
        logger.info(
            "Site-search lookup failed; falling back to discovery search",
            extra={"site_id": site_id, "error": str(exc)},
        )
        return []

    data_dict = data if isinstance(data, dict) else {}
    search_results_raw = data_dict.get("searchResults")
    search_results = search_results_raw if isinstance(search_results_raw, dict) else {}
    docs_raw = search_results.get("documents")
    docs = docs_raw if isinstance(docs_raw, list) else []
    results: list[dict[str, str]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        primary_key = doc.get("primaryKey")
        if not isinstance(primary_key, list) or len(primary_key) < 2:
            continue
        search_name = str(primary_key[0] or "").strip()
        record_type = str(primary_key[1] or "").strip()
        if not search_name or not record_type:
            continue

        found = doc.get("foundInFields") or {}
        display = doc.get("hyperlinkName") or ""
        if not display and isinstance(found, dict):
            candidates = (
                found.get("TEXT__search_displayName") or found.get("autocomplete") or []
            )
            if isinstance(candidates, list) and candidates:
                first_candidate = candidates[0]
                display = str(first_candidate) if first_candidate is not None else ""
        display_name = strip_html_tags(str(display or "")) or search_name

        desc_val = ""
        if isinstance(found, dict):
            descs = (
                found.get("TEXT__search_description")
                or found.get("TEXT__search_summary")
                or []
            )
            if isinstance(descs, list) and descs:
                desc_val = str(descs[0] or "")
        description = strip_html_tags(desc_val)

        results.append(
            {
                "name": search_name,
                "displayName": display_name,
                "description": description,
                "recordType": record_type,
            }
        )

    return results[:limit]


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
) -> list[dict[str, str]]:
    """Find searches matching a query term (name/description and sometimes detail text)."""
    discovery = get_discovery_service()
    # Prefer the same mechanism the web UI uses when no record type filter is provided.
    # This is higher-recall and returns canonical (searchName, recordType) pairs.
    if record_type is None:
        site_search_results = await _search_for_searches_via_site_search(site_id, query)
        if site_search_results:
            return site_search_results
    record_types: list[str] = []
    if isinstance(record_type, list):
        record_types = [str(rt) for rt in record_type if rt]
    elif isinstance(record_type, str) and record_type:
        record_types = [record_type]
    record_types = list(dict.fromkeys(record_types))
    if not record_types:
        record_types_raw = await discovery.get_record_types(site_id)
        record_types_list: list[str] = []
        for rt in record_types_raw:
            if not isinstance(rt, dict):
                continue
            url_seg_raw = rt.get("urlSegment")
            name_raw = rt.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            rt_name = url_seg or name or ""
            if rt_name:
                record_types_list.append(rt_name)
        record_types = record_types_list
        record_types = [rt for rt in record_types if rt]

    raw_terms = re.findall(r"[A-Za-z0-9]+", query or "")
    terms = [t.lower() for t in raw_terms if t]
    query_lower = query.lower() if query else ""
    matches: JSONArray = []

    def term_variants(term: str) -> list[str]:
        # Very small, cheap normalization for common user phrasing.
        # This is intentionally conservative (no heavy NLP deps).
        variants = {term}
        if len(term) > 3 and term.endswith("s"):
            variants.add(term[:-1])
        if len(term) > 4 and term.endswith("ed"):
            variants.add(term[:-2])
        if len(term) > 5 and term.endswith("ing"):
            variants.add(term[:-3])
        return list(variants)

    def add_matches(searches: JSONArray, rt_name: str) -> None:
        for search in searches:
            if not isinstance(search, dict):
                continue
            is_internal_raw = search.get("isInternal")
            if isinstance(is_internal_raw, bool) and is_internal_raw:
                continue
            display_name_raw = search.get("displayName")
            url_seg_raw = search.get("urlSegment")
            display_name = (
                display_name_raw if isinstance(display_name_raw, str) else ""
            ) or (url_seg_raw if isinstance(url_seg_raw, str) else "")
            desc_raw = search.get("description")
            desc = desc_raw if isinstance(desc_raw, str) else ""
            url_seg_raw2 = search.get("urlSegment")
            name_raw = search.get("name")
            url_segment = (url_seg_raw2 if isinstance(url_seg_raw2, str) else "") or (
                name_raw if isinstance(name_raw, str) else ""
            )
            internal_name_raw = search.get("name")
            internal_name = (
                internal_name_raw if isinstance(internal_name_raw, str) else ""
            )
            haystack = f"{display_name} {desc} {url_segment} {internal_name}".lower()
            score = 0
            if terms:
                score = sum(
                    1
                    for term in terms
                    if any(v in haystack for v in term_variants(term))
                )
            else:
                if query_lower and (
                    query_lower in display_name.lower()
                    or query_lower in desc.lower()
                    or query_lower in url_segment.lower()
                ):
                    score = 1
            if score > 0:
                url_seg_final_raw = search.get("urlSegment")
                name_final_raw = search.get("name")
                url_seg_final = (
                    url_seg_final_raw if isinstance(url_seg_final_raw, str) else None
                )
                name_final = name_final_raw if isinstance(name_final_raw, str) else ""
                matches.append(
                    {
                        "name": url_seg_final or name_final or "",
                        "displayName": display_name,
                        "description": desc,
                        "recordType": rt_name,
                        "score": str(score),
                    }
                )

    for rt_name in record_types:
        searches = await discovery.get_searches(site_id, rt_name)
        add_matches(searches, rt_name)

    def get_score(item: JSONValue) -> int:
        if not isinstance(item, dict):
            return 0
        score_raw = item.get("score")
        if isinstance(score_raw, str):
            try:
                return int(score_raw)
            except ValueError:
                return 0
        return 0

    def get_display_name(item: JSONValue) -> str:
        if not isinstance(item, dict):
            return ""
        display_name_raw = item.get("displayName")
        return display_name_raw if isinstance(display_name_raw, str) else ""

    matches.sort(key=lambda item: (-get_score(item), get_display_name(item)))
    result: list[dict[str, str]] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        item.pop("score", None)
        name_raw = item.get("name")
        display_name_raw = item.get("displayName")
        description_raw = item.get("description")
        record_type_raw = item.get("recordType")
        name = name_raw if isinstance(name_raw, str) else ""
        display_name = display_name_raw if isinstance(display_name_raw, str) else ""
        description = description_raw if isinstance(description_raw, str) else ""
        record_type = record_type_raw if isinstance(record_type_raw, str) else ""
        result.append(
            {
                "name": name,
                "displayName": display_name,
                "description": description,
                "recordType": record_type,
            }
        )
    return result[:20]


async def _resolve_record_type_for_search(
    client: VEuPathDBClient, record_type: str, search_name: str
) -> str:
    """Resolve which record type actually contains a search name."""
    try:
        record_types = await client.get_record_types()
    except Exception:
        return record_type
    ordered: list[str] = []
    for rt in record_types:
        rt_name: str | None = None
        if isinstance(rt, str):
            rt_name = rt
        elif isinstance(rt, dict):
            url_seg_raw = rt.get("urlSegment")
            name_raw = rt.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            rt_name = url_seg or name
        else:
            continue
        if not isinstance(rt_name, str):
            continue
        if rt_name == record_type:
            ordered.insert(0, rt_name)
        else:
            ordered.append(rt_name)
    for rt_name in ordered:
        try:
            searches = await client.get_searches(rt_name)
        except Exception:
            continue
        found = False
        for search in searches:
            if not isinstance(search, dict):
                continue
            url_seg_raw = search.get("urlSegment")
            name_raw = search.get("name")
            url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
            name = name_raw if isinstance(name_raw, str) else None
            if url_seg == search_name or name == search_name:
                found = True
                break
        if found:
            return rt_name
    return record_type
