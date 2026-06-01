"""Semantic similarity matching for search discovery.

Boosts search candidates by cosine similarity from a sentence-transformer
index, and injects high-similarity searches that keyword scoring missed.
"""

import asyncio

from pathfinder.integrations.embeddings.semantic_index import SemanticSearchIndex
from pathfinder.integrations.veupathdb.discovery_service import DiscoveryService
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.models import SearchMatch
from pathfinder.services.catalog.scoring import resolve_returns

logger = get_logger(__name__)

_SEMANTIC_BOOST = 15.0  # Max boost from semantic similarity (scaled by cosine)
_MIN_SEMANTIC_SIM = 0.3  # Minimum cosine similarity for semantic injection


def build_search_match(search: WDKSearch, rt: str) -> SearchMatch:
    """Build a SearchMatch from a WDKSearch for semantic injection."""
    display = search.display_name or search.url_segment
    category = ""
    dc = search.properties.get("displayCategory", [])
    if dc:
        category = str(dc[0])
    returns = resolve_returns(search.output_record_class_name)
    return SearchMatch(
        name=search.url_segment,
        display_name=display,
        description=search.summary or search.description,
        record_type=rt,
        category=category,
        returns=returns,
    )


async def apply_semantic_bonus(
    scored: list[tuple[float, SearchMatch]],
    discovery: DiscoveryService,
    site_id: str,
    query: str,
    record_types: list[str],
) -> None:
    """Boost scored entries by semantic similarity from the sentence-transformer index."""
    if not query:
        return
    try:
        catalog = await discovery.get_catalog(site_id)
        index = catalog.get_semantic_index()
        if not isinstance(index, SemanticSearchIndex):
            return

        rt_set = set(record_types)
        sem_results = await asyncio.to_thread(index.query, query, 50)
        sem_scores = {
            name: sim for name, rt, sim in sem_results if rt in rt_set or not rt_set
        }

        for i, (sc, entry) in enumerate(scored):
            sim = sem_scores.get(entry.name, 0.0)
            if sim > 0.0:
                scored[i] = (sc + _SEMANTIC_BOOST * sim, entry)

        # Inject high-similarity searches that weren't in keyword candidates
        existing_names = {entry.name for _, entry in scored}
        for search_name, rt, sim in sem_results:
            if search_name in existing_names or sim < _MIN_SEMANTIC_SIM:
                continue
            if rt not in rt_set and rt_set:
                continue
            search = catalog.find_search(rt, search_name)
            if search is None:
                continue
            scored.append((_SEMANTIC_BOOST * sim, build_search_match(search, rt)))
    except AppError, OSError, ValueError, TypeError:
        logger.debug("Semantic bonus failed (non-fatal)", exc_info=True)
