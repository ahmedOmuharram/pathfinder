"""Search listing and searching functions."""

import math
import re
from collections import Counter

import httpx

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.compile import ResolveRecordType
from veupath_chatbot.domain.strategy.tree import collect_plan_leaves
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.integrations.veupathdb.site_search import (
    query_site_search,
    strip_html_tags,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

_WEIGHT_SEARCH_NAME = 5.0
_WEIGHT_DISPLAY_NAME = 3.0
_WEIGHT_DESCRIPTION = 1.0
_KEYWORD_BOOST = 20.0
_MIN_TERM_LEN = 3
_MIN_PRIMARY_KEY_LENGTH = 2

_RECORD_CLASS_LABELS = {
    "transcript": "genes/transcripts",
    "gene": "genes",
    "snp": "SNPs",
    "popsetsequence": "popset sequences",
    "est": "ESTs",
    "compound": "compounds",
    "pathway": "pathways",
}


# ---------------------------------------------------------------------------
# Scoring, filtering, annotation
# ---------------------------------------------------------------------------


def score_search(
    *,
    query_terms: list[str],
    keywords: list[str],
    search_name: str,
    display_name: str,
    description: str,
    corpus_doc_count: int = 1,
    corpus_term_counts: dict[str, int] | None = None,
) -> float:
    """Score a search against query terms and keywords.

    1. Keywords matched against searchName via substring → ``+KEYWORD_BOOST`` each.
    2. Query terms matched per field with field weight x IDF.
    3. Short terms (< ``_MIN_TERM_LEN`` chars) ignored in query matching.
    """
    score = 0.0
    name_lower = search_name.lower()
    display_lower = display_name.lower()
    desc_lower = description.lower()

    for kw in keywords:
        if kw.lower() in name_lower:
            score += _KEYWORD_BOOST

    term_counts = corpus_term_counts or {}
    n = max(corpus_doc_count, 1)

    for term in query_terms:
        if len(term) < _MIN_TERM_LEN:
            continue
        term_lower = term.lower()
        df = term_counts.get(term_lower, 1)
        idf = math.log(n / (1 + df)) + 1.0

        if term_lower in name_lower:
            score += _WEIGHT_SEARCH_NAME * idf
        if term_lower in display_lower:
            score += _WEIGHT_DISPLAY_NAME * idf
        if term_lower in desc_lower:
            score += _WEIGHT_DESCRIPTION * idf

    return score


def is_chooser_search(search: JSONObject) -> bool:
    """Return True if this is a routing/chooser search (no real params).

    Chooser searches have ``websiteProperties: ["hideOperation"]`` and/or
    empty ``paramNames``.  The search list endpoint returns ``paramNames``
    (list of strings), not full ``parameters`` objects.
    """
    props = search.get("properties", {})
    if not isinstance(props, dict):
        return False
    ws_props = props.get("websiteProperties", [])
    if isinstance(ws_props, list) and "hideOperation" in ws_props:
        return True
    # paramNames is the list of param name strings from the search list endpoint.
    param_names = search.get("paramNames")
    return isinstance(param_names, list) and len(param_names) == 0


def annotate_search(search: JSONObject) -> dict[str, str]:
    """Add ``category`` and ``returns`` fields to a search result dict."""
    result: dict[str, str] = {}
    props = search.get("properties", {})
    if isinstance(props, dict):
        dc = props.get("displayCategory", [])
        if isinstance(dc, list) and dc:
            result["category"] = str(dc[0])
    rc = search.get("recordClassName") or search.get("outputRecordClassName", "")
    if isinstance(rc, str):
        rc_lower = rc.lower()
        for key, label in _RECORD_CLASS_LABELS.items():
            if key in rc_lower:
                result["returns"] = label
                break
    return result


async def get_raw_record_types(site_id: str) -> JSONArray:
    """Return raw WDK record type objects for a site.

    Unlike :func:`services.catalog.sites.get_record_types`, this preserves the
    full WDK payloads (``urlSegment``, ``name``, ``displayName``, etc.) so that
    callers needing the original structure don't have to go through the
    integrations layer directly.
    """
    discovery = get_discovery_service()
    return await discovery.get_record_types(site_id)


async def get_raw_searches(site_id: str, record_type: str) -> JSONArray:
    """Return raw WDK search objects for a record type.

    Thin service-level wrapper over the discovery integration so that AI tools
    and other service consumers never import from ``integrations/`` directly.
    """
    discovery = get_discovery_service()
    return await discovery.get_searches(site_id, record_type)


async def list_searches(site_id: str, record_type: str) -> list[dict[str, str]]:
    """List searches for a specific record type.

    Returns **name + displayName only** to keep the payload small (VEuPathDB
    has 2000+ searches; descriptions alone add ~3 MB).  The model should use
    ``search_for_searches`` for targeted discovery with descriptions, or
    ``get_search_parameters`` for full details on a specific search.
    """
    discovery = get_discovery_service()
    searches = await discovery.get_searches(site_id, record_type)
    result: list[dict[str, str]] = []
    for s in searches:
        if not isinstance(s, dict):
            continue
        is_internal_raw = s.get("isInternal")
        if isinstance(is_internal_raw, bool) and is_internal_raw:
            continue
        search_name = wdk_entity_name(s)
        display_name_raw = s.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else ""
        result.append(
            {
                "name": search_name,
                "displayName": display_name,
            }
        )
    return result


async def list_transforms(site_id: str, record_type: str) -> list[dict[str, str]]:
    """List transform/combine searches (with descriptions).

    Returns only searches that accept an input step — these are used to chain
    steps together (ortholog transform, weight filter, span logic, boolean
    combine, etc.).  Typically 5-7 per site, so descriptions are included.
    """
    discovery = get_discovery_service()
    searches = await discovery.get_searches(site_id, record_type)
    result: list[dict[str, str]] = []
    for s in searches:
        if not isinstance(s, dict):
            continue
        allowed = s.get("allowedPrimaryInputRecordClassNames")
        if not isinstance(allowed, list) or not allowed:
            continue
        is_internal_raw = s.get("isInternal")
        if isinstance(is_internal_raw, bool) and is_internal_raw:
            continue
        search_name = wdk_entity_name(s)
        display_name_raw = s.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else ""
        description_raw = s.get("description")
        description = description_raw if isinstance(description_raw, str) else ""
        result.append(
            {
                "name": search_name,
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
    except (httpx.HTTPError, AppError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "Site-search lookup failed; falling back to discovery search",
            site_id=site_id,
            error=str(exc),
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
        if (
            not isinstance(primary_key, list)
            or len(primary_key) < _MIN_PRIMARY_KEY_LENGTH
        ):
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

    # Boost transcript/gene results to the top — the model almost always
    # builds gene strategies, so EST/Popset/compound matches are noise.
    results.sort(key=lambda r: _record_type_priority(r.get("recordType", "")))

    # Deduplicate: same search can appear for multiple record types;
    # keep only the highest-priority (lowest sort key) occurrence.
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for r in results:
        if r["name"] not in seen:
            seen.add(r["name"])
            deduped.append(r)
    return deduped[:limit]


# Record types the model cares about most, in priority order.
_PREFERRED_RECORD_TYPES = ("transcript", "gene")


def _record_type_priority(record_type: str) -> int:
    """Lower = higher priority.  Transcript/gene first, everything else after."""
    rt = record_type.lower()
    for i, preferred in enumerate(_PREFERRED_RECORD_TYPES):
        if preferred in rt:
            return i
    return 100


async def _collect_search_candidates(
    discovery: object,
    site_id: str,
    record_types: list[str],
) -> list[tuple[JSONObject, str]]:
    """Collect all non-internal, non-chooser search candidates across record types."""
    candidates: list[tuple[JSONObject, str]] = []
    for rt_name in record_types:
        searches = await discovery.get_searches(site_id, rt_name)
        for s in searches:
            if not isinstance(s, dict):
                continue
            is_internal = s.get("isInternal")
            if isinstance(is_internal, bool) and is_internal:
                continue
            if is_chooser_search(s):
                continue
            candidates.append((s, rt_name))
    return candidates


def _score_candidates(
    candidates: list[tuple[JSONObject, str]],
    terms: list[str],
    kw_list: list[str],
) -> list[tuple[float, dict[str, str]]]:
    """Score each candidate search and return ``(score, entry)`` pairs."""
    corpus_counts: Counter[str] = Counter()
    for s, _ in candidates:
        name = wdk_entity_name(s)
        display = s.get("displayName", "")
        desc = s.get("description", "")
        haystack = f"{name} {display} {desc}".lower()
        for term in terms:
            if len(term) >= _MIN_TERM_LEN and term in haystack:
                corpus_counts[term] += 1

    doc_count = len(candidates)
    scored: list[tuple[float, dict[str, str]]] = []
    for s, rt_name in candidates:
        canonical_name = wdk_entity_name(s)
        display_raw = s.get("displayName")
        display = display_raw if isinstance(display_raw, str) else canonical_name
        desc_raw = s.get("description")
        desc = desc_raw if isinstance(desc_raw, str) else ""

        sc = score_search(
            query_terms=terms,
            keywords=kw_list,
            search_name=canonical_name,
            display_name=display,
            description=desc,
            corpus_doc_count=doc_count,
            corpus_term_counts=dict(corpus_counts),
        )
        if sc <= 0:
            continue

        annotations = annotate_search(s)
        entry: dict[str, str] = {
            "name": canonical_name,
            "displayName": display,
            "description": desc,
            "recordType": rt_name,
        }
        entry.update(annotations)
        scored.append((sc, entry))
    return scored


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
    *,
    keywords: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, str]]:
    """Find searches matching a query and/or keywords.

    Uses field-weighted scoring with IDF, keyword boosting against search
    names, chooser filtering, and result annotation. Site-search results
    are merged in when available.
    """
    kw_list = keywords or []
    discovery = get_discovery_service()

    # --- Resolve record types ---
    record_types: list[str] = []
    if isinstance(record_type, list):
        record_types = [str(rt) for rt in record_type if rt]
    elif isinstance(record_type, str) and record_type:
        record_types = [record_type]
    record_types = list(dict.fromkeys(record_types))
    if not record_types:
        record_types_raw = await discovery.get_record_types(site_id)
        record_types = [
            name for rt in record_types_raw if (name := wdk_entity_name(rt))
        ]

    raw_terms = re.findall(r"[A-Za-z0-9_]+", query or "")
    terms = [t.lower() for t in raw_terms if t]

    candidates = await _collect_search_candidates(discovery, site_id, record_types)
    scored = _score_candidates(candidates, terms, kw_list)

    # --- Merge site-search results (supplementary boost) ---
    try:
        site_results = await _search_for_searches_via_site_search(
            site_id, query, limit=limit
        )
        site_bonus: dict[str, float] = {}
        for rank, sr in enumerate(site_results):
            name = sr.get("name", "")
            if name and name not in site_bonus:
                site_bonus[name] = 5.0 / (1 + rank)

        for i, (sc, entry) in enumerate(scored):
            bonus = site_bonus.get(entry["name"], 0.0)
            if bonus > 0:
                scored[i] = (sc + bonus, entry)
    except httpx.HTTPError, AppError, ValueError, TypeError, KeyError:
        logger.debug("Site-search merge failed (non-fatal)")

    # --- Sort by score desc, then record type priority ---
    scored.sort(
        key=lambda item: (
            -item[0],
            _record_type_priority(item[1].get("recordType", "")),
            item[1].get("displayName", ""),
        )
    )

    # --- Deduplicate and cap ---
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for _, entry in scored:
        name = entry.get("name", "")
        if name in seen:
            continue
        seen.add(name)
        result.append(entry)
        if len(result) >= limit:
            break

    return result


async def find_record_type_for_search(
    site_id: str, record_type: str, search_name: str
) -> str:
    """Resolve which record type actually contains a search name.

    Uses the pre-cached SearchCatalog (mirrors WDK's global
    ``getQuestionByName()`` lookup) — no HTTP calls at resolve time.
    Falls back to *record_type* when the search isn't found.
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(site_id)
    resolved = catalog.find_record_type_for_search(search_name)
    return resolved or record_type


async def make_record_type_resolver(site_id: str) -> ResolveRecordType:
    """Create a record type resolver backed by the pre-cached SearchCatalog.

    Mirrors WDK's ``WdkModel.getQuestionByName()`` — a global lookup that
    finds which record type owns a given search name, using the already-cached
    catalog data (no HTTP calls at resolve time).
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(site_id)

    async def resolve(search_name: str) -> str | None:
        return catalog.find_record_type_for_search(search_name)

    return resolve


async def resolve_record_type_from_steps(
    root_step: PlanStepNode,
    resolver: ResolveRecordType,
) -> str | None:
    """Resolve record type from the first resolvable leaf search in a step tree.

    Uses :func:`collect_plan_leaves` to find leaf (search) nodes, then calls
    the resolver to find the owning record type for the first one that resolves.
    """
    for leaf in collect_plan_leaves(root_step):
        resolved = await resolver(leaf.search_name)
        if resolved:
            return resolved
    return None
