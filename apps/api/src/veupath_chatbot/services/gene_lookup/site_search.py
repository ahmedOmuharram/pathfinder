"""Site-search gene fetching and document parsing."""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.site_search import (
    query_site_search,
    strip_html_tags,
)
from veupath_chatbot.platform.types import JSONObject

from .organism import normalize_organism
from .result import build_gene_result

SITE_SEARCH_FETCH_LIMIT = 50


def parse_site_search_docs(docs: list[object]) -> list[JSONObject]:
    """Convert raw site-search documents into standardised gene dicts."""
    results: list[JSONObject] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue

        gene_id = strip_html_tags(str(doc.get("wdkPrimaryKeyString", ""))).strip()
        if not gene_id:
            pk = doc.get("primaryKey")
            if isinstance(pk, list) and pk:
                gene_id = str(pk[0]).strip()
        if not gene_id:
            continue

        summary = doc.get("summaryFieldData")
        if not isinstance(summary, dict):
            summary = {}

        doc_organism = normalize_organism(summary.get("TEXT__gene_organism_full", ""))
        doc_product = strip_html_tags(summary.get("TEXT__gene_product", ""))
        doc_gene_name = strip_html_tags(summary.get("TEXT__gene_name", ""))
        doc_gene_type = strip_html_tags(summary.get("TEXT__gene_type", ""))

        hyperlink_name = strip_html_tags(str(doc.get("hyperlinkName", ""))).strip()
        display_name = hyperlink_name or doc_gene_name or doc_product

        if not doc_organism and doc.get("organism"):
            doc_organism = normalize_organism(str(doc.get("organism", "")))

        found = doc.get("foundInFields")
        matched_fields: list[str] = []
        if isinstance(found, dict):
            for field_key, field_values in found.items():
                if isinstance(field_values, list) and field_values:
                    clean_key = field_key.replace("TEXT__", "").replace(
                        "MULTITEXT__", ""
                    )
                    matched_fields.append(clean_key)

        results.append(
            build_gene_result(
                gene_id=gene_id,
                display_name=display_name,
                organism=doc_organism,
                product=doc_product,
                gene_name=doc_gene_name,
                gene_type=doc_gene_type,
                matched_fields=matched_fields,
            )
        )
    return results


async def fetch_site_search_genes(
    site_id: str,
    search_text: str,
    *,
    organisms: list[str] | None = None,
    limit: int = SITE_SEARCH_FETCH_LIMIT,
) -> tuple[list[JSONObject], list[str], int]:
    """Run a single site-search query and return parsed results.

    :returns: ``(gene_results, available_organisms, total_count)``
    """
    data = await query_site_search(
        site_id,
        search_text=search_text,
        document_type="gene",
        organisms=organisms,
        limit=limit,
        offset=0,
    )
    data_dict = data if isinstance(data, dict) else {}
    sr_raw = data_dict.get("searchResults")
    sr = sr_raw if isinstance(sr_raw, dict) else {}
    total = sr.get("totalCount", 0)
    docs = sr.get("documents")
    doc_list = docs if isinstance(docs, list) else []

    results = parse_site_search_docs(doc_list)

    org_counts = data_dict.get("organismCounts")
    orgs = sorted(org_counts.keys()) if isinstance(org_counts, dict) else []

    return results, orgs, total if isinstance(total, int) else len(results)
