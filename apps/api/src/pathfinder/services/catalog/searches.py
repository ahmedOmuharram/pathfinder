"""Search listing, filtering, and discovery. Scoring, semantic matching, and
candidate collection live in sibling modules."""

import re
from collections.abc import Awaitable, Callable

from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.tree import collect_plan_leaves
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.models import SearchMatch
from pathfinder.services.catalog.scoring import (
    is_chooser_search,
    record_type_priority,
    score_candidates,
)
from pathfinder.services.catalog.search_collection import (
    apply_site_search_bonus,
    collect_search_candidates,
    resolve_record_types,
)
from pathfinder.services.catalog.semantic_matching import apply_semantic_bonus

logger = get_logger(__name__)

# A search name is unique across all record types on a site.
ResolveRecordType = Callable[[str], Awaitable[str | None]]


async def get_raw_record_types(site_id: str) -> list[WDKRecordType]:
    """Return the full WDK record type objects for a site."""
    discovery = get_discovery_service()
    return await discovery.get_record_types(site_id)


async def get_raw_searches(site_id: str, record_type: str) -> list[WDKSearch]:
    """Return the raw WDK search objects for a record type."""
    discovery = get_discovery_service()
    return await discovery.get_searches(site_id, record_type)


async def browse_search_categories(
    site_id: str,
    record_type: str = "transcript",
) -> list[dict[str, str | int | list[str]]]:
    """Return the ontology search categories with example search names.

    Searches with no category form one universal group.
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(site_id)
    searches = await discovery.get_searches(site_id, record_type)

    groups: dict[str, list[str]] = {}
    for s in searches:
        if s.full_name.startswith("InternalQuestions."):
            continue
        if is_chooser_search(s):
            continue
        cat = catalog.get_search_category(s.url_segment) or "(universal)"
        groups.setdefault(cat, []).append(s.display_name or s.url_segment)

    result: list[dict[str, str | int | list[str]]] = []
    for cat in sorted(groups, key=lambda c: (c == "(universal)", -len(groups[c]))):
        # Universal searches are few, so they are all listed.
        max_examples = len(groups[cat]) if cat == "(universal)" else 5
        result.append(
            {
                "category": cat,
                "count": len(groups[cat]),
                "examples": groups[cat][:max_examples],
            }
        )
    return result


async def list_searches(site_id: str, record_type: str) -> list[dict[str, str]]:
    """List searches for a record type.

    Only names are returned, because descriptions make the payload large.
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
    """List the searches that accept an input step, with their descriptions.

    These searches chain one step onto another.
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


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
    *,
    keywords: list[str] | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[SearchMatch]:
    """Find searches that match a query or keywords.

    A category restricts the candidates to that category plus the
    universal searches.
    """
    kw_list = keywords or []
    discovery = get_discovery_service()

    record_types = await resolve_record_types(discovery, site_id, record_type)

    raw_terms = re.findall(r"[A-Za-z0-9_]+", query or "")
    terms = [t.lower() for t in raw_terms if t]

    candidates = await collect_search_candidates(
        discovery, site_id, record_types, category=category
    )
    scored = score_candidates(candidates, terms, kw_list)

    await apply_site_search_bonus(scored, site_id, query, limit)

    await apply_semantic_bonus(scored, discovery, site_id, query, record_types)

    scored.sort(
        key=lambda item: (
            -item[0],
            record_type_priority(item[1].record_type),
            item[1].display_name,
        )
    )

    # Relevance is the score normalized against the best score.
    max_score = scored[0][0] if scored else 1.0
    if max_score <= 0:
        max_score = 1.0

    seen: set[str] = set()
    result: list[SearchMatch] = []
    for sc, entry in scored:
        if entry.name in seen:
            continue
        seen.add(entry.name)
        result.append(
            SearchMatch(
                name=entry.name,
                display_name=entry.display_name,
                description=entry.description,
                record_type=entry.record_type,
                category=entry.category,
                returns=entry.returns,
                relevance=sc / max_score,
            )
        )
        if len(result) >= limit:
            break

    return result


async def find_record_type_for_search(ctx: SearchContext) -> str:
    """Resolve which record type owns a search name.

    The context record type applies when the search is not in the catalog.
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(ctx.site_id)
    resolved = catalog.find_record_type_for_search(ctx.search_name)
    return resolved or ctx.record_type


async def make_record_type_resolver(site_id: str) -> ResolveRecordType:
    """Create a record type resolver over the cached search catalog.

    The resolver makes no HTTP calls.
    """
    discovery = get_discovery_service()
    catalog = await discovery.get_catalog(site_id)

    async def resolve(search_name: str) -> str | None:
        return catalog.find_record_type_for_search(search_name)

    return resolve


async def resolve_record_type_from_steps(
    root_step: StrategyStepNode,
    resolver: ResolveRecordType,
) -> str | None:
    """Resolve the record type from the first leaf search that resolves."""
    for leaf in collect_plan_leaves(root_step):
        resolved = await resolver(leaf.search_name)
        if resolved:
            return resolved
    return None
