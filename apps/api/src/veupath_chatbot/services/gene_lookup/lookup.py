"""Main gene text lookup orchestration.

Uses four concurrent strategies to maximise recall, then scores, deduplicates,
and ranks results by relevance:

A. Unrestricted site-search (Solr) -- always fires.
B. Organism-restricted site-search -- fires when the query implies an organism.
C. WDK ``GenesByText`` wildcard -- fires when query looks like a gene ID prefix.
D. WDK ``GenesByText`` broad -- fires when an explicit organism filter is given.
"""

from __future__ import annotations

import asyncio
from typing import cast

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.search_rerank import (
    ScoredResult,
    analyse_query,
    dedup_and_sort,
)

from .enrich import enrich_sparse_gene_results
from .organism import score_organism_match, suggest_organisms
from .scoring import score_gene_relevance
from .site_search import SITE_SEARCH_FETCH_LIMIT, fetch_site_search_genes
from .wdk import (
    WDK_TEXT_FIELDS_BROAD,
    WDK_TEXT_FIELDS_ID,
    WDK_WILDCARD_LIMIT,
    WdkTextResult,
    fetch_wdk_text_genes,
)

logger = get_logger(__name__)


async def lookup_genes_by_text(
    site_id: str,
    query: str,
    *,
    organism: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> JSONObject:
    """Search for gene records using multiple concurrent strategies.

    :param site_id: VEuPathDB site identifier (e.g. ``"plasmodb"``).
    :param query: Free-text query -- gene name, symbol, locus tag, or description.
    :param organism: Optional organism filter.
    :param offset: Number of results to skip (for pagination).
    :param limit: Maximum number of results to return.
    :returns: Dict with ``results``, ``totalCount``, and optional ``suggestedOrganisms``.
    """
    needed = offset + limit

    # --- Strategy A: unrestricted site-search ---
    # PlasmoDB 500s when numRecords > 50, so always cap at SITE_SEARCH_FETCH_LIMIT.
    # Additional results come from WDK strategies below.
    try:
        (
            primary_results,
            available_organisms,
            total_count,
        ) = await fetch_site_search_genes(
            site_id,
            query,
            limit=SITE_SEARCH_FETCH_LIMIT,
        )
    except Exception as exc:
        logger.warning(
            "Gene text lookup via site-search failed; falling back to WDK strategies",
            site_id=site_id,
            query=query,
            error=str(exc),
        )
        primary_results = []
        available_organisms = []

    intent = analyse_query(
        query,
        available_organisms,
        organism_scorer=score_organism_match,
    )

    explicit_organism: str | None = None
    if organism:
        organism_lower = organism.strip().lower()
        for avail in available_organisms:
            if avail.lower() == organism_lower:
                explicit_organism = avail
                break

    effective_organism = explicit_organism or intent.implied_organism

    logger.debug(
        "Gene search intent",
        query=query,
        is_gene_id_like=intent.is_gene_id_like,
        implied_organism=intent.implied_organism,
        explicit_organism=explicit_organism,
        wildcard_ids=intent.wildcard_ids,
    )

    # --- Strategy B: organism-restricted site-search ---
    async def _strategy_b() -> list[JSONObject]:
        if not effective_organism:
            return []
        try:
            results, _, _ = await fetch_site_search_genes(
                site_id,
                query,
                organisms=[effective_organism],
                limit=SITE_SEARCH_FETCH_LIMIT,
            )
            return results
        except Exception as exc:
            logger.debug(
                "Organism-restricted gene search failed (non-fatal)",
                site_id=site_id,
                organism=effective_organism,
                error=str(exc),
            )
            return []

    # --- Strategy C: WDK wildcard ID search ---
    async def _strategy_c() -> WdkTextResult:
        if not intent.wildcard_ids or not effective_organism:
            return WdkTextResult(records=[], total_count=0)
        try:
            return await fetch_wdk_text_genes(
                site_id,
                list(intent.wildcard_ids),
                organism=effective_organism,
                text_fields=WDK_TEXT_FIELDS_ID,
                limit=max(WDK_WILDCARD_LIMIT, needed),
            )
        except Exception as exc:
            logger.debug(
                "WDK wildcard gene search failed (non-fatal)",
                site_id=site_id,
                wildcard_ids=intent.wildcard_ids,
                error=str(exc),
            )
            return WdkTextResult(records=[], total_count=0)

    # --- Strategy D: WDK broad text search ---
    async def _strategy_d() -> WdkTextResult:
        if not explicit_organism:
            return WdkTextResult(records=[], total_count=0)
        try:
            return await fetch_wdk_text_genes(
                site_id,
                [query],
                organism=explicit_organism,
                text_fields=WDK_TEXT_FIELDS_BROAD,
                limit=max(WDK_WILDCARD_LIMIT, needed),
            )
        except Exception as exc:
            logger.debug(
                "WDK broad text gene search failed (non-fatal)",
                site_id=site_id,
                query=query,
                organism=explicit_organism,
                error=str(exc),
            )
            return WdkTextResult(records=[], total_count=0)

    # Run strategies B, C, D concurrently (A already completed above).
    organism_results, wdk_id_result, wdk_broad_result = await asyncio.gather(
        _strategy_b(),
        _strategy_c(),
        _strategy_d(),
    )

    # Merge all results and enrich sparse ones.
    all_raw = (
        primary_results
        + organism_results
        + wdk_id_result.records
        + wdk_broad_result.records
    )
    all_raw = await enrich_sparse_gene_results(site_id, all_raw, len(all_raw))

    # Score, deduplicate, sort by relevance.
    scored: list[ScoredResult] = [
        ScoredResult(
            result=r,
            score=score_gene_relevance(query, r),
            source="site-search",
        )
        for r in all_raw
    ]
    ranked = dedup_and_sort(
        scored,
        key_fn=lambda r: str(r.get("geneId", "")).strip(),
    )
    results: list[JSONObject] = [sr.result for sr in ranked]

    # Apply organism filtering / suggestions.
    suggested_organisms: list[str] | None = None

    if organism:
        organism_input = organism.strip()
        ol = organism_input.lower()

        if explicit_organism:
            results = [
                r
                for r in results
                if isinstance(r, dict)
                and str(r.get("organism", "")).strip().lower() == ol
            ]
        else:
            suggested_organisms = suggest_organisms(organism_input, available_organisms)
            if not suggested_organisms:
                results = []
                suggested_organisms = available_organisms[:10]

    paginated = results[offset : offset + limit]

    authoritative_total = max(
        len(results),
        wdk_broad_result.total_count,
        wdk_id_result.total_count,
    )

    response: dict[str, object] = {
        "results": paginated,
        "totalCount": authoritative_total,
    }
    if suggested_organisms:
        response["suggestedOrganisms"] = suggested_organisms

    return cast(JSONObject, response)


async def batch_lookup_genes_by_text(
    site_id: str,
    queries: list[str],
    *,
    organisms: list[str] | str | None = None,
    per_query_limit: int = 10,
    total_limit: int = 50,
) -> JSONObject:
    """Run multiple gene text lookups concurrently and merge the results."""
    if not queries:
        return {"queryResults": [], "results": [], "totalCount": 0}

    if isinstance(organisms, str):
        org_list = [organisms] * len(queries)
    else:
        org_list = organisms or []

    semaphore = asyncio.Semaphore(3)

    async def _run_single(idx: int, q: str) -> JSONObject:
        org = org_list[idx].strip() if idx < len(org_list) and org_list[idx] else None
        async with semaphore:
            return await lookup_genes_by_text(
                site_id,
                q,
                organism=org or None,
                limit=per_query_limit,
            )

    raw_results = await asyncio.gather(
        *(_run_single(i, q) for i, q in enumerate(queries)),
        return_exceptions=True,
    )

    query_results: list[JSONObject] = []
    combined: list[JSONObject] = []

    for idx, result in enumerate(raw_results):
        if isinstance(result, BaseException):
            logger.warning(
                "Batch gene lookup failed for query",
                query=queries[idx],
                error=str(result),
            )
            entry = cast(
                JSONObject,
                {
                    "query": queries[idx],
                    "organism": org_list[idx] if idx < len(org_list) else None,
                    "results": [],
                    "totalCount": 0,
                    "error": str(result),
                },
            )
        else:
            result_dict = result if isinstance(result, dict) else {}
            results_list = result_dict.get("results")
            if not isinstance(results_list, list):
                results_list = []
            entry = cast(
                JSONObject,
                {
                    "query": queries[idx],
                    "organism": org_list[idx] if idx < len(org_list) else None,
                    "results": results_list,
                    "totalCount": result_dict.get("totalCount", len(results_list)),
                },
            )
            combined.extend(results_list)

        query_results.append(entry)

    return cast(
        JSONObject,
        {
            "queryResults": query_results,
            "results": combined[:total_limit],
            "totalCount": len(combined),
        },
    )
