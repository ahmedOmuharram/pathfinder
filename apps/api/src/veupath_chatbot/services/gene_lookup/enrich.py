"""Enrich sparse gene results with WDK metadata."""

from collections.abc import Callable

from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.text import strip_html_tags
from veupath_chatbot.platform.types import JSONObject

from .organism import normalize_organism
from .wdk import resolve_gene_ids

logger = get_logger(__name__)

# Fields to fill from WDK metadata when absent in the original result.
# Each entry is (field_name, transform_fn).
_ENRICHMENT_FIELDS: list[tuple[str, Callable[[str], str]]] = [
    ("organism", normalize_organism),
    ("product", strip_html_tags),
    ("geneName", strip_html_tags),
    ("geneType", str),
    ("location", str),
]


def _merge_meta(merged: JSONObject, meta: JSONObject) -> None:
    """Fill empty fields in *merged* from *meta*, applying transforms."""
    for field, transform in _ENRICHMENT_FIELDS:
        if not merged.get(field) and meta.get(field):
            merged[field] = transform(str(meta[field]))
    if not merged.get("displayName"):
        merged["displayName"] = str(
            merged.get("geneName")
            or merged.get("product")
            or meta.get("product")
            or merged.get("geneId")
            or ""
        )


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
    except AppError as exc:
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
        _merge_meta(merged, meta)
        enriched.append(merged)

    return enriched[:limit]
