"""Standalone catalog discovery tools for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`CatalogTools` methods exactly.
"""

from typing import cast

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.query_validation import search_query_error
from pathfinder.ai.tools.standalone._catalog_models import _UNIVERSAL_SEARCHES
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.platform.types import JSONObject
from pathfinder.services import catalog
from pathfinder.services.catalog.public_strategy_search import (
    rank_public_strategies,
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
    record_type: str | None = None,
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
            Must include 5+ specific keywords -- be as descriptive as possible.
            Example: 'gametocyte RNA-Seq differential expression DESeq analysis'
        record_type: Filter to a specific record type (e.g., 'transcript'). Omit for all.
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
    results: list[JSONObject] = cast(
        "list[JSONObject]", [m.to_dict() for m in matches],
    )

    seen = {str(r["name"]) for r in results}
    results.extend(
        u
        for u in _UNIVERSAL_SEARCHES
        if str(u["name"]) not in seen
    )

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
        record_type: Record type (e.g., 'transcript'). Defaults to transcript.
    """
    return await catalog.browse_search_categories(ctx.deps.site_id, record_type)


async def list_searches(
    ctx: RunContext[AgentDeps],
    record_type: str,
) -> list[dict[str, str]]:
    """List all search names for a record type (names only, no descriptions).

    Use search_for_searches first for targeted discovery with descriptions.

    Args:
        ctx: Agent run context.
        record_type: Record type (e.g., 'gene', 'transcript').
    """
    return await catalog.list_searches(ctx.deps.site_id, record_type)


async def list_transforms(
    ctx: RunContext[AgentDeps],
    record_type: str,
) -> list[dict[str, str]]:
    """List available transform and combine operations (with descriptions).

    Returns searches that chain onto a previous step's results -- such as
    ortholog transforms, weight filters, span logic, and boolean combines.

    Args:
        ctx: Agent run context.
        record_type: Record type (e.g., 'transcript').
    """
    return await catalog.list_transforms(ctx.deps.site_id, record_type)


async def lookup_phyletic_codes(
    ctx: RunContext[AgentDeps],
    record_type: str,
    query: str,
) -> JSONObject | ToolErrorPayload:
    """Look up phyletic species/group codes by name for GenesByOrthologPattern.

    Returns {code, label, leaf} triples. Use codes in profile_pattern:
    %CODE:Y% (include) or %CODE:N% (exclude).

    Args:
        ctx: Agent run context.
        record_type: Record type (usually 'transcript').
        query: Species or clade name to search for (e.g., 'falciparum', 'human',
            'Apicomplexa'). Returns matching codes for use in profile_pattern.
    """
    return await catalog.lookup_phyletic_codes(ctx.deps.site_id, record_type, query)


async def search_example_plans(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 3,
) -> list[JSONObject]:
    """Retrieve relevant public strategies from WDK matched by text relevance.

    Args:
        ctx: Agent run context.
        query: User goal / query to match against public strategies.
        limit: Max number of results to return.
    """
    try:
        api = get_strategy_api(ctx.deps.site_id)
        public_strategies = await api.list_public_strategies()
        return rank_public_strategies(public_strategies, query=query, limit=limit)
    except (AppError, OSError) as exc:
        logger.warning("Failed to fetch public strategies", error=str(exc))
        return []
