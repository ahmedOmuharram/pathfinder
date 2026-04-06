"""Search listing, filtering, and discovery functions.

Public API for search catalog operations.  Scoring, semantic matching,
and candidate-collection logic live in sibling modules ``scoring``,
``semantic_matching``, and ``search_collection``.
"""

import re
from collections.abc import Awaitable, Callable

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.tree import collect_plan_leaves
from veupath_chatbot.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.catalog.models import SearchMatch
from veupath_chatbot.services.catalog.scoring import (
    is_chooser_search,
    record_type_priority,
    score_candidates,
)
from veupath_chatbot.services.catalog.search_collection import (
    apply_site_search_bonus,
    collect_search_candidates,
    resolve_record_types,
)
from veupath_chatbot.services.catalog.semantic_matching import apply_semantic_bonus

logger = get_logger(__name__)

# Callback type: given a search name, returns the owning record type (or None).
# Mirrors WDK's WdkModel.getQuestionByName() -- a global lookup across all
# record types.
ResolveRecordType = Callable[[str], Awaitable[str | None]]


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


async def browse_search_categories(
    site_id: str,
    record_type: str = "transcript",
) -> list[dict[str, str | int | list[str]]]:
    """Return ontology-based search categories with example search names.

    Groups searches by their ``searchCategory-*`` subcategory from the site's
    ontology.  Uncategorized (universal) searches are returned as a separate
    group.  Each group includes the category key, a count, and up to 5 example
    display names so the model can see what vocabulary to use when querying.
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
        # Show all names for universal searches (they're few and critical),
        # but only 5 examples for dataset-specific categories (hundreds each).
        max_examples = len(groups[cat]) if cat == "(universal)" else 5
        result.append({
            "category": cat,
            "count": len(groups[cat]),
            "examples": groups[cat][:max_examples],
        })
    return result


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


async def search_for_searches(
    site_id: str,
    record_type: str | list[str] | None,
    query: str,
    *,
    keywords: list[str] | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[SearchMatch]:
    """Find searches matching a query and/or keywords.

    Uses field-weighted scoring with IDF, keyword boosting against search
    names, chooser filtering, result annotation, and semantic similarity
    from a sentence-transformer index over enriched search descriptions.

    When *category* is set to a ``searchCategory-*`` value from the site's
    ontology, only searches in that subcategory (plus universal searches)
    are considered.  This dramatically narrows the search space for
    dataset-specific queries.
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

    # --- Semantic similarity boost ---
    await apply_semantic_bonus(scored, discovery, site_id, query, record_types)

    # --- Sort by score desc, then record type priority ---
    scored.sort(
        key=lambda item: (
            -item[0],
            record_type_priority(item[1].record_type),
            item[1].display_name,
        )
    )

    # --- Normalize scores to 0-1 relevance ---
    max_score = scored[0][0] if scored else 1.0
    if max_score <= 0:
        max_score = 1.0

    # --- Deduplicate, attach relevance, and cap ---
    seen: set[str] = set()
    result: list[SearchMatch] = []
    for sc, entry in scored:
        if entry.name in seen:
            continue
        seen.add(entry.name)
        result.append(SearchMatch(
            name=entry.name,
            display_name=entry.display_name,
            description=entry.description,
            record_type=entry.record_type,
            category=entry.category,
            returns=entry.returns,
            relevance=sc / max_score,
        ))
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
