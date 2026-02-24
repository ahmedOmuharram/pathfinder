"""Enrich sparse gene results with WDK metadata."""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.site_search import strip_html_tags
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

from .organism import normalize_organism
from .wdk import resolve_gene_ids

logger = get_logger(__name__)


async def enrich_sparse_gene_results(
    site_id: str,
    results: list[JSONObject],
    limit: int,
) -> list[JSONObject]:
    """Enrich results that lack organism/product via WDK standard reporter.

    Site-search only returns ``summaryFieldData`` for fields where the query
    matched.  When a gene matches in literature (e.g. MULTIgene_PubMed),
    organism/product are absent.  We fetch full metadata from the WDK to fill
    the gaps.
    """
    ids_to_enrich: list[str] = [
        str(r["geneId"])
        for r in results
        if isinstance(r, dict)
        and r.get("geneId")
        and (not r.get("organism") or not r.get("product"))
    ]
    if not ids_to_enrich:
        return results

    try:
        resolved = await resolve_gene_ids(
            site_id,
            ids_to_enrich[:50],
            record_type="transcript",
        )
    except Exception as exc:
        logger.debug(
            "Gene enrichment via WDK skipped",
            site_id=site_id,
            count=len(ids_to_enrich),
            error=str(exc),
        )
        return results

    if resolved.get("error"):
        return results

    records = resolved.get("records")
    if not isinstance(records, list) or not records:
        return results

    by_id: dict[str, JSONObject] = {}
    for rec in records:
        if isinstance(rec, dict) and rec.get("geneId"):
            by_id[str(rec["geneId"]).strip()] = rec

    enriched: list[JSONObject] = []
    for r in results:
        if not isinstance(r, dict):
            enriched.append(r)
            continue
        gene_id = r.get("geneId")
        meta = by_id.get(str(gene_id or "")) if gene_id else None
        if not meta:
            enriched.append(r)
            continue

        merged = dict(r)
        if not merged.get("organism") and meta.get("organism"):
            merged["organism"] = normalize_organism(str(meta["organism"]))
        if not merged.get("product") and meta.get("product"):
            merged["product"] = strip_html_tags(str(meta["product"]))
        if not merged.get("geneName") and meta.get("geneName"):
            merged["geneName"] = strip_html_tags(str(meta["geneName"]))
        if not merged.get("geneType") and meta.get("geneType"):
            merged["geneType"] = str(meta["geneType"])
        if not merged.get("location") and meta.get("location"):
            merged["location"] = str(meta["location"])
        if not merged.get("displayName"):
            merged["displayName"] = str(
                merged.get("geneName")
                or merged.get("product")
                or meta.get("product")
                or gene_id
                or ""
            )
        enriched.append(merged)

    return enriched[:limit]
