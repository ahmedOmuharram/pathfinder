"""Standalone gene record lookup tools for pydantic-ai migration."""

from pydantic_ai import RunContext

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.services.gene_lookup import (
    GeneResolveResult,
    GeneSearchResult,
    lookup_genes_by_text,
    resolve_gene_ids,
)

_MAX_GENE_IDS = 200


async def lookup_gene_records(
    ctx: RunContext[AgentDeps],
    query: str,
    organism: str | None = None,
    limit: int = 10,
) -> GeneSearchResult:
    """Look up gene records by name, symbol, or description using VEuPathDB site-search.

    Use this to resolve human-readable gene names (from literature or user input)
    to VEuPathDB gene IDs.  The returned IDs can then be used as positive/negative
    controls in `run_control_tests` or `optimize_search_parameters`.

    Args:
        ctx: Agent run context.
        query: Free-text query to search for gene records -- gene name, symbol,
            locus tag, product description, or keyword (e.g. 'PfAP2-G',
            'gametocyte surface antigen', 'Pfs25').
        organism: Organism filter (e.g. 'Plasmodium falciparum 3D7').
            Omit to search across all organisms on the site.
        limit: Max results to return (default 10).
    """
    return await lookup_genes_by_text(
        ctx.deps.site_id,
        query,
        organism=organism,
        limit=max(1, min(limit, 50)),
    )


async def resolve_gene_ids_to_records(
    ctx: RunContext[AgentDeps],
    gene_ids: list[str],
    record_type: str = "transcript",
    search_name: str = "GeneByLocusTag",
    param_name: str = "ds_gene_ids",
) -> GeneResolveResult:
    """Resolve known gene IDs to full records (product name, organism, gene type).

    Use this to validate gene IDs or fetch metadata for IDs you already have
    (e.g. from literature).  For discovering genes by name, use `lookup_gene_records` instead.

    Args:
        ctx: Agent run context.
        gene_ids: List of gene/locus tag IDs to resolve (e.g.
            ['PF3D7_1222600', 'PF3D7_1031000']).
        record_type: WDK record type (default 'transcript').
        search_name: WDK search that accepts ID lists (default 'GeneByLocusTag').
        param_name: Parameter name for the ID list (default 'ds_gene_ids').
    """
    ids = [str(x).strip() for x in (gene_ids or []) if str(x).strip()]
    if not ids:
        return GeneResolveResult(
            records=[], total_count=0, error="No gene IDs provided."
        )
    if len(ids) > _MAX_GENE_IDS:
        return GeneResolveResult(
            records=[],
            total_count=0,
            error=f"Too many IDs (max {_MAX_GENE_IDS}). Reduce the list.",
        )
    return await resolve_gene_ids(
        ctx.deps.site_id,
        ids,
        record_type=record_type,
        search_name=search_name,
        param_name=param_name,
    )
