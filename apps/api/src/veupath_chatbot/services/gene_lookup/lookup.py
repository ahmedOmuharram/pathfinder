"""Main gene text lookup orchestration.

Uses four concurrent strategies to maximise recall, then scores, deduplicates,
and ranks results by relevance:

A. Unrestricted site-search (Solr) -- always fires.
B. Organism-restricted site-search -- fires when the query implies an organism.
C. WDK ``GenesByText`` wildcard -- fires when query looks like a gene ID prefix.
D. WDK ``GenesByText`` broad -- fires when an explicit organism filter is given.
"""

import asyncio
from typing import cast

import httpx

from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.search_rerank import (
    QueryIntent,
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

_MIN_WORDS_FOR_MULTI_WORD = 2

_EMPTY_WDK = WdkTextResult(records=[], total_count=0)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _run_primary_searches(
    site_id: str,
    query: str,
    *,
    is_multi_word: bool,
) -> tuple[list[JSONObject], list[str], int]:
    """Run strategy A (unrestricted) and A2 (phrase-quoted) concurrently.

    :returns: ``(merged_results, available_organisms, total_count)``
    """

    async def _strategy_a() -> tuple[list[JSONObject], list[str], int]:
        try:
            return await fetch_site_search_genes(
                site_id,
                query,
                limit=SITE_SEARCH_FETCH_LIMIT,
            )
        except (httpx.HTTPError, AppError) as exc:
            logger.warning(
                "Gene text lookup via site-search failed; falling back to WDK strategies",
                site_id=site_id,
                query=query,
                error=str(exc),
            )
            return [], [], 0

    async def _strategy_a_phrase() -> list[JSONObject]:
        if not is_multi_word:
            return []
        try:
            results, _, _ = await fetch_site_search_genes(
                site_id,
                f'"{query.strip()}"',
                limit=SITE_SEARCH_FETCH_LIMIT,
            )
        except (httpx.HTTPError, AppError) as exc:
            logger.warning(
                "Phrase-quoted gene search failed", query=query, error=str(exc)
            )
            return []
        else:
            return results

    (
        (primary_results, available_organisms, total_count),
        phrase_results,
    ) = await asyncio.gather(_strategy_a(), _strategy_a_phrase())

    # Phrase results come first -- they are more precise for multi-word queries.
    if phrase_results:
        primary_results = phrase_results + primary_results

    return primary_results, available_organisms, total_count


async def _run_supplementary_searches(
    site_id: str,
    query: str,
    intent: QueryIntent,
    *,
    effective_organism: str | None,
    explicit_organism: str | None,
    needed: int,
) -> tuple[list[JSONObject], WdkTextResult, WdkTextResult]:
    """Run strategies B, C, D concurrently.

    :returns: ``(organism_results, wdk_id_result, wdk_broad_result)``
    """

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
        except (httpx.HTTPError, AppError) as exc:
            logger.debug(
                "Organism-restricted gene search failed (non-fatal)",
                site_id=site_id,
                organism=effective_organism,
                error=str(exc),
            )
            return []
        else:
            return results

    async def _strategy_c() -> WdkTextResult:
        if not intent.wildcard_ids or not effective_organism:
            return _EMPTY_WDK
        try:
            return await fetch_wdk_text_genes(
                site_id,
                list(intent.wildcard_ids),
                organism=effective_organism,
                text_fields=WDK_TEXT_FIELDS_ID,
                limit=max(WDK_WILDCARD_LIMIT, needed),
            )
        except AppError as exc:
            logger.debug(
                "WDK wildcard gene search failed (non-fatal)",
                site_id=site_id,
                wildcard_ids=intent.wildcard_ids,
                error=str(exc),
            )
            return _EMPTY_WDK

    async def _strategy_d() -> WdkTextResult:
        if not explicit_organism:
            return _EMPTY_WDK
        try:
            return await fetch_wdk_text_genes(
                site_id,
                [query],
                organism=explicit_organism,
                text_fields=WDK_TEXT_FIELDS_BROAD,
                limit=max(WDK_WILDCARD_LIMIT, needed),
            )
        except AppError as exc:
            logger.debug(
                "WDK broad text gene search failed (non-fatal)",
                site_id=site_id,
                query=query,
                organism=explicit_organism,
                error=str(exc),
            )
            return _EMPTY_WDK

    return await asyncio.gather(_strategy_b(), _strategy_c(), _strategy_d())


async def _merge_and_rank(
    site_id: str,
    query: str,
    all_raw: list[JSONObject],
) -> list[JSONObject]:
    """Enrich sparse results, score, deduplicate, and sort by relevance."""
    enriched = await enrich_sparse_gene_results(site_id, all_raw, len(all_raw))

    scored: list[ScoredResult] = [
        ScoredResult(
            result=r,
            score=score_gene_relevance(query, r),
            source="site-search",
        )
        for r in enriched
    ]
    ranked = dedup_and_sort(
        scored,
        key_fn=lambda r: str(r.get("geneId", "")).strip(),
    )
    return [sr.result for sr in ranked]


def _apply_organism_filter(
    results: list[JSONObject],
    *,
    organism: str | None,
    explicit_organism: str | None,
    available_organisms: list[str],
) -> tuple[list[JSONObject], list[str] | None]:
    """Filter results by organism and generate suggestions when needed.

    :returns: ``(filtered_results, suggested_organisms)``
    """
    if not organism:
        return results, None

    organism_input = organism.strip()
    ol = organism_input.lower()

    if explicit_organism:
        filtered = [
            r
            for r in results
            if isinstance(r, dict) and str(r.get("organism", "")).strip().lower() == ol
        ]
        return filtered, None

    suggested = suggest_organisms(organism_input, available_organisms)
    if not suggested:
        return [], available_organisms[:10]
    return results, suggested


def _build_response(
    *,
    paginated: list[JSONObject],
    total_count: int,
    wdk_totals: tuple[int, int],
    suggested_organisms: list[str] | None,
) -> JSONObject:
    """Build the final JSON response dict.

    :param wdk_totals: ``(wdk_id_total, wdk_broad_total)``
    """
    authoritative_total = max(total_count, *wdk_totals)

    response: dict[str, object] = {
        "records": paginated,
        "totalCount": authoritative_total,
    }
    if suggested_organisms:
        response["suggestedOrganisms"] = suggested_organisms

    return cast("JSONObject", response)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    is_multi_word = len(query.strip().split()) >= _MIN_WORDS_FOR_MULTI_WORD

    # Phase 1: primary site-search (strategies A + A2).
    primary_results, available_organisms, _total_count = await _run_primary_searches(
        site_id,
        query,
        is_multi_word=is_multi_word,
    )

    # Analyse intent and resolve organism.
    intent = analyse_query(
        query, available_organisms, organism_scorer=score_organism_match
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

    # Phase 2: supplementary searches (strategies B, C, D).
    (
        organism_results,
        wdk_id_result,
        wdk_broad_result,
    ) = await _run_supplementary_searches(
        site_id,
        query,
        intent,
        effective_organism=effective_organism,
        explicit_organism=explicit_organism,
        needed=needed,
    )

    # Phase 3: merge, enrich, score, deduplicate.
    all_raw = (
        primary_results
        + organism_results
        + wdk_id_result.records
        + wdk_broad_result.records
    )
    results = await _merge_and_rank(site_id, query, all_raw)

    # Phase 4: organism filtering.
    results, suggested_organisms = _apply_organism_filter(
        results,
        organism=organism,
        explicit_organism=explicit_organism,
        available_organisms=available_organisms,
    )

    # Phase 5: paginate and build response.
    paginated = results[offset : offset + limit]

    return _build_response(
        paginated=paginated,
        total_count=len(results),
        wdk_totals=(wdk_id_result.total_count, wdk_broad_result.total_count),
        suggested_organisms=suggested_organisms,
    )
