"""Agent tools for catalog discovery: record types, searches, categories,
transforms, phyletic codes, and example public strategies."""

from typing import cast

from assistant_core.memory.embedding import embed_text
from assistant_core.platform.logging import get_logger
from assistant_core.platform.types import JSONObject
from pydantic_ai import RunContext

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.query_validation import search_query_error
from pathfinder.ai.tools.standalone._catalog_models import _UNIVERSAL_SEARCHES
from pathfinder.platform.errors import AppError
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services import catalog
from pathfinder.services.catalog.public_strategy_search import (
    rank_public_strategies,
    rank_public_strategies_semantic,
)
from pathfinder.services.wdk import get_strategy_api

logger = get_logger(__name__)


async def get_record_types(
    ctx: RunContext[AgentDeps],
) -> list[dict[str, str]]:
    """List available record types for this site."""
    record_types = await catalog.get_record_types(ctx.deps.site_id)
    return [
        {
            "name": rt.name,
            "displayName": rt.display_name,
            "description": rt.description,
        }
        for rt in record_types
    ]


async def search_for_searches(
    ctx: RunContext[AgentDeps],
    query: str,
    record_type: str = "transcript",
    keywords: list[str] | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[JSONObject]:
    """Find WDK searches by description and/or keywords.

    Returns a ranked list with name, displayName, description, category,
    what the search returns, and a relevance score (0-1, higher is better).
    Prefer searches with higher relevance scores.

    Args:
        ctx: Agent run context.
        query: Descriptive natural language query about what you're looking for.
            Be as descriptive as possible for better results.
            Example: 'gametocyte RNA-Seq differential expression DESeq analysis'
        record_type: Record type to search. Defaults to 'transcript' (gene searches).
            Use 'snp', 'pathway', 'compound', etc. for non-gene searches.
        keywords: Optional exact identifiers to match against search names (urlSegment).
            These get massive score boost. Extract from dataset names, search
            name fragments, or organism codes mentioned in the user's request.
            Example: ['Su_strand_specific', 'Percentile', 'pfal3D7']
        category: Filter to a specific search subcategory from the site ontology.
        limit: Max results to return.
    """
    kw = keywords or []
    err = search_query_error(query, has_keywords=bool(kw))
    if err is not None:
        return [err]
    matches = await catalog.search_for_searches(
        ctx.deps.site_id,
        record_type=record_type,
        query=query,
        keywords=kw,
        category=category,
        limit=limit,
    )
    results: list[JSONObject] = cast("list[JSONObject]", [m.to_dict() for m in matches])

    decided = ctx.deps.agent_state.decided_search_names()
    hidden = sorted({str(r["name"]) for r in results if str(r["name"]) in decided})
    results = [r for r in results if str(r["name"]) not in decided]

    seen = {str(r["name"]) for r in results}
    results.extend(u for u in _UNIVERSAL_SEARCHES if str(u["name"]) not in seen)

    ctx.deps.agent_state.record_catalog_searches(
        [str(r["name"]) for r in results if "name" in r]
    )

    if hidden:
        note: JSONObject = {
            "note": (
                f"{len(hidden)} already-decided search(es) hidden: {hidden}. "
                "You've already recorded a decision on these; don't re-evaluate."
            ),
        }
        results.append(note)

    return results


async def browse_search_categories(
    ctx: RunContext[AgentDeps],
    record_type: str = "transcript",
) -> list[dict[str, str | int | list[str]]]:
    """Browse available search categories and their example searches.

    Call this BEFORE search_for_searches to see what categories and search
    names exist on this site.  Returns categories grouped by the site's
    ontology, each with a count and up to 5 example display names.
    Use the category key as the 'category' parameter in search_for_searches.
    Use the example display names to formulate better search queries.

    Args:
        ctx: Agent run context.
        record_type: Record type. Defaults to 'transcript' (gene searches).
            Use 'snp', 'pathway', etc. for non-gene searches.
    """
    return await catalog.browse_search_categories(ctx.deps.site_id, record_type)


async def list_searches(
    ctx: RunContext[AgentDeps],
    record_type: str = "transcript",
) -> list[dict[str, str]]:
    """List all search names (names only, no descriptions).

    Use search_for_searches first for targeted discovery with descriptions.

    Args:
        ctx: Agent run context.
        record_type: Record type. Defaults to 'transcript' (gene searches).
    """
    rows = await catalog.list_searches(ctx.deps.site_id, record_type)
    decided = ctx.deps.agent_state.decided_search_names()
    visible = [r for r in rows if r.get("name") not in decided]
    ctx.deps.agent_state.record_catalog_searches(
        [str(r["name"]) for r in visible if r.get("name")]
    )
    return visible


async def list_transforms(
    ctx: RunContext[AgentDeps],
    record_type: str = "transcript",
) -> list[dict[str, str]]:
    """List available transform and combine operations (with descriptions).

    Returns searches that chain onto a previous step's results -- such as
    ortholog transforms, weight filters, span logic, and boolean combines.

    Args:
        ctx: Agent run context.
        record_type: Record type. Defaults to 'transcript'.
    """
    return await catalog.list_transforms(ctx.deps.site_id, record_type)


async def lookup_phyletic_codes(
    ctx: RunContext[AgentDeps],
    query: str,
    record_type: str = "transcript",
) -> JSONObject | ToolErrorPayload:
    """Look up phyletic species/clade codes by name for GenesByOrthologPattern.

    Returns {code, label, leaf} triples. Put a code or its label in
    included_species or excluded_species; profile_pattern is derived from those
    two lists and is never written by hand.

    Args:
        ctx: Agent run context.
        query: Species or clade name to search for (e.g., 'falciparum', 'human',
            'Apicomplexa'). A code with leaf=false is a clade and selects every
            species under it.
        record_type: Record type. Defaults to 'transcript'.
    """
    return await catalog.lookup_phyletic_codes(ctx.deps.site_id, record_type, query)


async def search_example_plans(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 3,
) -> list[JSONObject]:
    """Retrieve relevant public strategies from WDK, ranked by semantic
    similarity to the query (falls back to lexical token overlap if the
    embedding model is unavailable).

    Args:
        ctx: Agent run context.
        query: User goal / query to match against public strategies.
        limit: Max number of results to return.
    """
    try:
        api = get_strategy_api(ctx.deps.site_id)
        public_strategies = await api.list_public_strategies()
    except (AppError, OSError) as exc:
        logger.warning("Failed to fetch public strategies", error=str(exc))
        return []
    try:
        return await rank_public_strategies_semantic(
            public_strategies, query, embed=embed_text, limit=limit
        )
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning(
            "Semantic strategy ranking unavailable; using lexical fallback",
            error=str(exc),
        )
        return rank_public_strategies(public_strategies, query=query, limit=limit)
