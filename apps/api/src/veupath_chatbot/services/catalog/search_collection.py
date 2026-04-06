"""Candidate collection, filtering, and site-search integration for search discovery.

Internal helpers used by the public ``search_for_searches`` orchestrator in
``searches.py``.  These handle:

- Collecting WDK search candidates (with optional ontology category filtering)
- Resolving record-type arguments (including gene→transcript aliasing)
- Parsing site-search documents into SearchMatch objects
- Boosting scored entries by site-search rank
"""

from veupath_chatbot.integrations.veupathdb.discovery_service import DiscoveryService
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
    SiteSearchDocument,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.text import strip_html_tags
from veupath_chatbot.services.catalog.models import SearchMatch
from veupath_chatbot.services.catalog.scoring import (
    is_chooser_search,
    record_type_priority,
)

logger = get_logger(__name__)

_MIN_PRIMARY_KEY_LENGTH = 2


def parse_site_search_doc(doc: SiteSearchDocument) -> SearchMatch | None:
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
        found.get("TEXT__search_summary") or found.get("TEXT__search_description") or []
    )
    desc_val = str(descs[0]) if descs else ""
    description = strip_html_tags(desc_val)

    return SearchMatch(
        name=search_name,
        display_name=display_name,
        description=description,
        record_type=record_type,
    )


async def search_for_searches_via_site_search(
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
        entry = parse_site_search_doc(doc)
        if entry is not None:
            results.append(entry)

    # Boost transcript/gene results to the top — the model almost always
    # builds gene strategies, so EST/Popset/compound matches are noise.
    results.sort(key=lambda r: record_type_priority(r.record_type))

    # Deduplicate: same search can appear for multiple record types;
    # keep only the highest-priority (lowest sort key) occurrence.
    seen: set[str] = set()
    deduped: list[SearchMatch] = []
    for r in results:
        if r.name not in seen:
            seen.add(r.name)
            deduped.append(r)
    return deduped[:limit]


async def collect_search_candidates(
    discovery: DiscoveryService,
    site_id: str,
    record_types: list[str],
    category: str | None = None,
) -> list[tuple[WDKSearch, str]]:
    """Collect search candidates, optionally filtered by ontology category.

    When *category* is set, only searches belonging to that ``searchCategory-*``
    subcategory are included — plus all universal (uncategorized) searches so
    the model always has access to GenesByText, GenesByTaxon, etc.
    """
    catalog = await discovery.get_catalog(site_id)
    candidates: list[tuple[WDKSearch, str]] = []
    for rt_name in record_types:
        searches = await discovery.get_searches(site_id, rt_name)
        for s in searches:
            if s.full_name.startswith("InternalQuestions."):
                continue
            if is_chooser_search(s):
                continue
            if category:
                search_cat = catalog.get_search_category(s.url_segment)
                # Include if: matches category OR is universal (no category)
                if search_cat is not None and search_cat != category:
                    continue
            candidates.append((s, rt_name))
    return candidates


async def resolve_record_types(
    discovery: DiscoveryService, site_id: str, record_type: str | list[str] | None
) -> list[str]:
    """Resolve the record_type argument to a deduplicated list of type strings.

    When the caller asks for ``"gene"`` we also include ``"transcript"``
    because most VEuPathDB gene searches (especially dataset-specific ones)
    live under the transcript record type.  Without this, passing
    ``record_type="gene"`` silently hides the majority of useful searches.
    """
    record_types: list[str] = []
    if isinstance(record_type, list):
        record_types = [str(rt) for rt in record_type if rt]
    elif isinstance(record_type, str) and record_type:
        record_types = [record_type]
    record_types = list(dict.fromkeys(record_types))
    # Most VEuPathDB gene searches (especially dataset-specific ones) live
    # under "transcript".  When the model asks for "gene", also include
    # "transcript" so those searches aren't silently hidden.
    if "gene" in record_types and "transcript" not in record_types:
        record_types.append("transcript")
    if not record_types:
        typed_rts = await discovery.get_record_types(site_id)
        record_types = [rt.url_segment for rt in typed_rts if rt.url_segment]
    return record_types


async def apply_site_search_bonus(
    scored: list[tuple[float, SearchMatch]],
    site_id: str,
    query: str,
    limit: int,
) -> None:
    """Best-effort: boost scored entries by their rank in site-search results."""
    try:
        site_results = await search_for_searches_via_site_search(
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
