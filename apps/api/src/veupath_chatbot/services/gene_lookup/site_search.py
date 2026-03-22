"""Site-search gene fetching and document parsing."""

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
    SiteSearchDocument,
)
from veupath_chatbot.platform.text import strip_html_tags

from .organism import normalize_organism
from .result import GeneResult

SITE_SEARCH_FETCH_LIMIT = 50


def _extract_gene_id(doc: SiteSearchDocument) -> str:
    """Extract the gene ID from a site-search document."""
    gene_id = strip_html_tags(doc.wdk_primary_key_string).strip()
    if not gene_id and doc.primary_key:
        gene_id = doc.primary_key[0].strip()
    return gene_id


def _extract_matched_fields(doc: SiteSearchDocument) -> list[str]:
    """Extract matched field names from a site-search document."""
    matched_fields: list[str] = []
    for field_key, field_values in doc.found_in_fields.items():
        if field_values:
            clean_key = field_key.replace("MULTITEXT__", "").replace("TEXT__", "")
            matched_fields.append(clean_key)
    return matched_fields


def parse_site_search_docs(docs: list[SiteSearchDocument]) -> list[GeneResult]:
    """Convert typed site-search documents into standardised gene results."""
    results: list[GeneResult] = []
    for doc in docs:
        gene_id = _extract_gene_id(doc)
        if not gene_id:
            continue

        summary = doc.summary_field_data

        doc_organism = normalize_organism(str(summary.get("TEXT__gene_organism_full", "")))
        doc_product = strip_html_tags(str(summary.get("TEXT__gene_product", "")))
        doc_gene_name = strip_html_tags(str(summary.get("TEXT__gene_name", "")))
        doc_gene_type = strip_html_tags(str(summary.get("TEXT__gene_type", "")))

        hyperlink_name = strip_html_tags(doc.hyperlink_name).strip()
        display_name = hyperlink_name or doc_gene_name or doc_product

        if not doc_organism and doc.organism:
            doc_organism = normalize_organism(doc.organism[0])

        results.append(
            GeneResult(
                gene_id=gene_id,
                display_name=display_name,
                organism=doc_organism,
                product=doc_product,
                gene_name=doc_gene_name,
                gene_type=doc_gene_type,
                matched_fields=_extract_matched_fields(doc),
            )
        )
    return results


async def fetch_site_search_genes(
    site_id: str,
    search_text: str,
    *,
    organisms: list[str] | None = None,
    limit: int = SITE_SEARCH_FETCH_LIMIT,
) -> tuple[list[GeneResult], list[str], int]:
    """Run a single site-search query and return parsed results.

    :returns: ``(gene_results, available_organisms, total_count)``
    """
    response = await get_site_router().get_site_search_client(site_id).search(
        search_text,
        document_type_filter=DocumentTypeFilter(document_type="gene"),
        organisms=organisms,
        limit=limit,
        offset=0,
    )

    results = parse_site_search_docs(response.search_results.documents)
    orgs = sorted(response.organism_counts.keys())
    total = response.search_results.total_count

    return results, orgs, total
