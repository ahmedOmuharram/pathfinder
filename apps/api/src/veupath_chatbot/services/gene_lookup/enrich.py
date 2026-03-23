"""Enrich sparse gene results with WDK metadata."""

from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.text import strip_html_tags

from .organism import normalize_organism
from .result import GeneResult
from .wdk import resolve_gene_ids

logger = get_logger(__name__)


def _merge_meta(merged: GeneResult, meta: GeneResult) -> GeneResult:
    """Fill empty fields in *merged* from *meta*, applying transforms."""
    return GeneResult(
        gene_id=merged.gene_id,
        display_name=(
            merged.display_name
            or merged.gene_name
            or merged.product
            or meta.product
            or merged.gene_id
        ),
        organism=merged.organism or normalize_organism(meta.organism),
        product=merged.product or strip_html_tags(meta.product),
        gene_name=merged.gene_name or strip_html_tags(meta.gene_name),
        gene_type=merged.gene_type or meta.gene_type,
        location=merged.location or meta.location,
        previous_ids=merged.previous_ids,
        matched_fields=merged.matched_fields,
    )


async def enrich_sparse_gene_results(
    site_id: str,
    results: list[GeneResult],
    limit: int,
) -> list[GeneResult]:
    """Enrich results that lack organism/product via WDK standard reporter.

    Site-search only returns ``summaryFieldData`` for fields where the query
    matched.  When a gene matches in literature (e.g. MULTIgene_PubMed),
    organism/product are absent.  We fetch full metadata from the WDK to fill
    the gaps.
    """
    ids_to_enrich: list[str] = [
        r.gene_id for r in results if r.gene_id and (not r.organism or not r.product)
    ]
    if not ids_to_enrich:
        return results

    try:
        resolved = await resolve_gene_ids(
            site_id,
            ids_to_enrich[:50],
            record_type="transcript",
        )
    except AppError as exc:
        logger.debug(
            "Gene enrichment via WDK skipped",
            site_id=site_id,
            count=len(ids_to_enrich),
            error=str(exc),
        )
        return results

    if resolved.error:
        return results

    if not resolved.records:
        return results

    by_id: dict[str, GeneResult] = {}
    for rec in resolved.records:
        if rec.gene_id:
            by_id[rec.gene_id.strip()] = rec

    enriched: list[GeneResult] = []
    for r in results:
        meta = by_id.get(r.gene_id) if r.gene_id else None
        if not meta:
            enriched.append(r)
            continue
        enriched.append(_merge_meta(r, meta))

    return enriched[:limit]
