"""Search listing and searching functions."""

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.compile import ResolveRecordType
from veupath_chatbot.domain.strategy.tree import collect_plan_leaves
from veupath_chatbot.integrations.veupathdb.discovery import (
    DiscoveryService,
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
    SiteSearchDocument,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.text import strip_html_tags
from veupath_chatbot.services.catalog.models import SearchMatch

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


@dataclass
class SearchCorpus:
    """Corpus statistics for IDF scoring in search ranking."""

    doc_count: int = 1
    term_counts: dict[str, int] = field(default_factory=dict)


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
    corpus: SearchCorpus | None = None,
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

    sc = corpus or SearchCorpus()
    term_counts = sc.term_counts
    n = max(sc.doc_count, 1)

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


def is_chooser_search(search: WDKSearch) -> bool:
    """Return True if this is a routing/chooser search (no real params).

    Chooser searches have ``websiteProperties: ["hideOperation"]``.
    """
    ws_props = search.properties.get("websiteProperties", [])
    return "hideOperation" in ws_props


async def get_raw_record_types(site_id: str) -> list[WDKRecordType]:
    """Return typed WDK record type objects for a site.

    Unlike :func:`services.catalog.sites.get_record_types`, this preserves the
    full WDK model (``url_segment``, ``display_name``, ``searches``, etc.) so
    that callers needing the complete structure don't have to go through the
    integrations layer directly.
    """
    discovery = get_discovery_service()
    return await discovery.get_record_types(site_id)


async def get_raw_searches(site_id: str, record_type: str) -> list[WDKSearch]:
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
        if s.full_name.startswith("InternalQuestions."):
            continue
        result.append(
            {
                "name": s.url_segment,
                "displayName": s.display_name,
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
        if not s.allowed_primary_input_record_class_names:
            continue
        if s.full_name.startswith("InternalQuestions."):
            continue
        result.append(
            {
                "name": s.url_segment,
                "displayName": s.display_name,
                "description": s.description,
            }
        )
    return result


def _parse_site_search_doc(doc: SiteSearchDocument) -> SearchMatch | None:
    """Parse a single site-search document into a SearchMatch, or None to skip."""
    if len(doc.primary_key) < _MIN_PRIMARY_KEY_LENGTH:
        return None
    search_name = doc.primary_key[0].strip()
    record_type = doc.primary_key[1].strip()
    if not search_name or not record_type:
        return None

    found = doc.found_in_fields
    display = doc.hyperlink_name
    if not display:
        candidates = (
            found.get("TEXT__search_displayName") or found.get("autocomplete") or []
        )
        if candidates:
            display = str(candidates[0]) if candidates[0] is not None else ""
    display_name = strip_html_tags(display) or search_name

    descs = (
        found.get("TEXT__search_description") or found.get("TEXT__search_summary") or []
    )
    desc_val = str(descs[0]) if descs else ""
    description = strip_html_tags(desc_val)

    return SearchMatch(
        name=search_name,
        display_name=display_name,
        description=description,
        record_type=record_type,
    )


async def _search_for_searches_via_site_search(
    site_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[SearchMatch]:
    """Search WDK searches via the site's /site-search service.

    This mirrors the webapp search UI (`/app/search`) when filtering to
    documentType=search.
    """
    try:
        response = (
            await get_site_router()
            .get_site_search_client(site_id)
            .search(
                query,
                document_type_filter=DocumentTypeFilter(document_type="search"),
                limit=limit,
                offset=0,
            )
        )
    except AppError as exc:
        logger.warning(
            "Site-search lookup failed; falling back to discovery search",
            site_id=site_id,
            error=str(exc),
        )
        return []

    results: list[SearchMatch] = []
    for doc in response.search_results.documents:
        entry = _parse_site_search_doc(doc)
        if entry is not None:
            results.append(entry)

    # Boost transcript/gene results to the top — the model almost always
    # builds gene strategies, so EST/Popset/compound matches are noise.
    results.sort(key=lambda r: _record_type_priority(r.record_type))

    # Deduplicate: same search can appear for multiple record types;
    # keep only the highest-priority (lowest sort key) occurrence.
    seen: set[str] = set()
    deduped: list[SearchMatch] = []
    for r in results:
        if r.name not in seen:
            seen.add(r.name)
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
    discovery: DiscoveryService,
    site_id: str,
    record_types: list[str],
) -> list[tuple[WDKSearch, str]]:
    """Collect all non-internal, non-chooser search candidates across record types."""
    candidates: list[tuple[WDKSearch, str]] = []
    for rt_name in record_types:
        searches = await discovery.get_searches(site_id, rt_name)
        for s in searches:
            if s.full_name.startswith("InternalQuestions."):
                continue
            if is_chooser_search(s):
                continue
            candidates.append((s, rt_name))
    return candidates


def _score_candidates(
    candidates: list[tuple[WDKSearch, str]],
    terms: list[str],
    kw_list: list[str],
) -> list[tuple[float, SearchMatch]]:
    """Score each candidate search and return ``(score, entry)`` pairs."""
    corpus_counts: Counter[str] = Counter()
    for s, _ in candidates:
        haystack = f"{s.url_segment} {s.display_name} {s.description}".lower()
        for term in terms:
            if len(term) >= _MIN_TERM_LEN and term in haystack:
                corpus_counts[term] += 1

    doc_count = len(candidates)
    scored: list[tuple[float, SearchMatch]] = []
    for s, rt_name in candidates:
        display = s.display_name or s.url_segment
        desc = s.description

        sc = score_search(
            query_terms=terms,
            keywords=kw_list,
            search_name=s.url_segment,
            display_name=display,
            description=desc,
            corpus=SearchCorpus(doc_count=doc_count, term_counts=dict(corpus_counts)),
        )
        if sc <= 0:
            continue

        # Inline annotation (category + returns)
        category = ""
        dc = s.properties.get("displayCategory", [])
        if dc:
            category = str(dc[0])
        returns = ""
        rc = s.output_record_class_name
        if rc:
            rc_lower = rc.lower()
            for key, label in _RECORD_CLASS_LABELS.items():
                if key in rc_lower:
                    returns = label
                    break

        entry = SearchMatch(
            name=s.url_segment,
            display_name=display,
            description=desc,
            record_type=rt_name,
            category=category,
            returns=returns,
        )
        scored.append((sc, entry))
    return scored


async def _resolve_record_types(
    discovery: DiscoveryService, site_id: str, record_type: str | list[str] | None
) -> list[str]:
    """Resolve the record_type argument to a deduplicated list of type strings."""
    record_types: list[str] = []
    if isinstance(record_type, list):
        record_types = [str(rt) for rt in record_type if rt]
    elif isinstance(record_type, str) and record_type:
        record_types = [record_type]
    record_types = list(dict.fromkeys(record_types))
    if not record_types:
        typed_rts = await discovery.get_record_types(site_id)
        record_types = [rt.url_segment for rt in typed_rts if rt.url_segment]
    return record_types


async def _apply_site_search_bonus(
    scored: list[tuple[float, SearchMatch]],
    site_id: str,
    query: str,
    limit: int,
) -> None:
    """Best-effort: boost scored entries by their rank in site-search results."""
    try:
        site_results = await _search_for_searches_via_site_search(
            site_id, query, limit=limit
        )
        site_bonus: dict[str, float] = {}
        for rank, sr in enumerate(site_results):
            if sr.name and sr.name not in site_bonus:
                site_bonus[sr.name] = 5.0 / (1 + rank)

        for i, (sc, entry) in enumerate(scored):
            bonus = site_bonus.get(entry.name, 0.0)
            if bonus > 0:
                scored[i] = (sc + bonus, entry)
    except AppError:
        logger.debug("Site-search merge failed (non-fatal)")


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
    *,
    keywords: list[str] | None = None,
    limit: int = 20,
) -> list[SearchMatch]:
    """Find searches matching a query and/or keywords.

    Uses field-weighted scoring with IDF, keyword boosting against search
    names, chooser filtering, and result annotation. Site-search results
    are merged in when available.
    """
    kw_list = keywords or []
    discovery = get_discovery_service()

    record_types = await _resolve_record_types(discovery, site_id, record_type)

    raw_terms = re.findall(r"[A-Za-z0-9_]+", query or "")
    terms = [t.lower() for t in raw_terms if t]

    candidates = await _collect_search_candidates(discovery, site_id, record_types)
    scored = _score_candidates(candidates, terms, kw_list)

    await _apply_site_search_bonus(scored, site_id, query, limit)

    # --- Sort by score desc, then record type priority ---
    scored.sort(
        key=lambda item: (
            -item[0],
            _record_type_priority(item[1].record_type),
            item[1].display_name,
        )
    )

    # --- Deduplicate and cap ---
    seen: set[str] = set()
    result: list[SearchMatch] = []
    for _, entry in scored:
        if entry.name in seen:
            continue
        seen.add(entry.name)
        result.append(entry)
        if len(result) >= limit:
            break

    return result


async def find_record_type_for_search(ctx: SearchContext) -> str:
    """Resolve which record type actually contains a search name.

    Uses the pre-cached SearchCatalog (mirrors WDK's global
    ``getQuestionByName()`` lookup) — no HTTP calls at resolve time.
    Falls back to ``ctx.record_type`` when the search isn't found.
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(ctx.site_id)
    resolved = catalog.find_record_type_for_search(ctx.search_name)
    return resolved or ctx.record_type


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
