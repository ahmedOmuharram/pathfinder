"""Gene record lookup service.

Provides two complementary lookup strategies:

1. **Text search** — uses VEuPathDB site-search (Solr) to find genes by name,
   symbol, product description, or any free text.  Best for resolving human-
   readable names (e.g. "PfAP2-G", "Pfs25") to VEuPathDB gene IDs.

2. **ID resolution** — uses the WDK stateless standard reporter endpoint
   (``POST /record-types/{rt}/searches/{search}/reports/standard``) to fetch
   metadata for a list of known gene IDs.  Useful for validating IDs or
   retrieving product names / organisms for IDs obtained from literature.

Both approaches are read-only and do not create steps or strategies.
"""

from __future__ import annotations

from typing import cast

from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.site_search import (
    query_site_search,
    strip_html_tags,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)

# Default attributes to request for gene records via the standard reporter.
_DEFAULT_GENE_ATTRIBUTES = [
    "primary_key",
    "gene_product",
    "organism",
    "gene_type",
]


async def lookup_genes_by_text(
    site_id: str,
    query: str,
    *,
    record_type: str | None = None,
    limit: int = 20,
) -> JSONObject:
    """Search for gene records by free text using VEuPathDB site-search.

    Returns a compact list of matching gene records with IDs, organism, and
    product descriptions.  This is the primary way for the planner to resolve
    gene names / symbols to VEuPathDB IDs.

    :param site_id: VEuPathDB site identifier (e.g. ``"plasmodb"``).
    :param query: Free-text query — gene name, symbol, locus tag, or description.
    :param record_type: Optional document type filter (defaults to ``"gene"``).
    :param limit: Maximum number of results to return.
    :returns: Dict with ``results`` list and ``totalCount``.
    """
    doc_type = record_type or "gene"
    try:
        data = await query_site_search(
            site_id,
            search_text=query,
            document_type=doc_type,
            limit=limit,
            offset=0,
        )
    except Exception as exc:
        logger.warning(
            "Gene text lookup via site-search failed",
            site_id=site_id,
            query=query,
            error=str(exc),
        )
        return {
            "results": [],
            "totalCount": 0,
            "error": f"Site-search unavailable: {exc}",
        }

    data_dict = data if isinstance(data, dict) else {}
    search_results_raw = data_dict.get("searchResults")
    search_results = search_results_raw if isinstance(search_results_raw, dict) else {}
    total_count = search_results.get("totalCount", 0)
    docs_raw = search_results.get("documents")
    docs = docs_raw if isinstance(docs_raw, list) else []

    results: list[JSONObject] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue

        # Primary key — for gene records this is typically [source_id, project_id]
        primary_key = doc.get("primaryKey")
        if not isinstance(primary_key, list) or not primary_key:
            continue

        gene_id = str(primary_key[0]).strip() if primary_key else ""
        project = str(primary_key[1]).strip() if len(primary_key) > 1 else ""
        if not gene_id:
            continue

        # Display name (often the gene symbol or product)
        display_name = strip_html_tags(str(doc.get("hyperlinkName") or ""))

        # Extract useful fields from foundInFields
        found = doc.get("foundInFields") or {}
        organism = ""
        product = ""
        matched_fields: list[str] = []

        if isinstance(found, dict):
            for field_key, field_values in found.items():
                if not isinstance(field_values, list):
                    continue
                clean_key = field_key.replace("TEXT__", "")
                if clean_key in ("organism", "gene_organism_full"):
                    organism = (
                        strip_html_tags(str(field_values[0])) if field_values else ""
                    )
                elif clean_key in ("product", "gene_product"):
                    product = (
                        strip_html_tags(str(field_values[0])) if field_values else ""
                    )
                if field_values:
                    matched_fields.append(clean_key)

        results.append(
            cast(
                JSONObject,
                {
                    "geneId": gene_id,
                    "project": project,
                    "displayName": display_name,
                    "organism": organism,
                    "product": product,
                    "matchedFields": matched_fields,
                },
            )
        )

    return cast(
        JSONObject,
        {
            "results": results[:limit],
            "totalCount": total_count if isinstance(total_count, int) else len(results),
        },
    )


async def resolve_gene_ids(
    site_id: str,
    gene_ids: list[str],
    *,
    record_type: str = "transcript",
    search_name: str = "GeneByLocusTag",
    param_name: str = "ds_gene_ids",
    attributes: list[str] | None = None,
) -> JSONObject:
    """Resolve a list of gene IDs to full records via the WDK standard reporter.

    Uses the **stateless** WDK endpoint (no steps/strategies created):
    ``POST /record-types/{rt}/searches/{search}/reports/standard``

    This follows the same pattern as VEuPathDB's official API example notebooks.

    :param site_id: VEuPathDB site identifier.
    :param gene_ids: List of gene/locus tag IDs to look up.
    :param record_type: WDK record type (default ``"transcript"``).
    :param search_name: WDK search that accepts an ID list (default ``"GeneByLocusTag"``).
    :param param_name: Parameter name for the ID list (default ``"ds_gene_ids"``).
    :param attributes: Attributes to request (defaults to common gene attributes).
    :returns: Dict with ``records`` list and ``totalCount``.
    """
    if not gene_ids:
        return {"records": [], "totalCount": 0}

    client = get_wdk_client(site_id)
    attrs = attributes or _DEFAULT_GENE_ATTRIBUTES

    # GeneByLocusTag typically uses an input-dataset parameter — upload IDs
    # as a dataset first, then reference the dataset ID.
    try:
        # Step 1: Upload IDs as a dataset
        dataset_resp = await client.post(
            "/users/current/datasets",
            json=cast(
                JSONObject,
                {"sourceType": "idList", "sourceContent": {"ids": gene_ids}},
            ),
        )
        if not isinstance(dataset_resp, dict):
            return {
                "records": [],
                "totalCount": 0,
                "error": "Failed to create dataset for ID lookup.",
            }
        dataset_id = dataset_resp.get("id")
        if dataset_id is None:
            return {
                "records": [],
                "totalCount": 0,
                "error": "Dataset creation returned no ID.",
            }

        # Step 2: Query the standard reporter (stateless — no steps needed)
        answer = await client.post(
            f"/record-types/{record_type}/searches/{search_name}/reports/standard",
            json=cast(
                JSONObject,
                {
                    "searchConfig": {
                        "parameters": {param_name: str(dataset_id)},
                    },
                    "reportConfig": {
                        "attributes": attrs,
                        "tables": [],
                    },
                },
            ),
        )
    except Exception as exc:
        logger.warning(
            "Gene ID resolution via standard reporter failed",
            site_id=site_id,
            gene_ids_count=len(gene_ids),
            error=str(exc),
        )
        return {
            "records": [],
            "totalCount": 0,
            "error": f"WDK lookup failed: {exc}",
        }

    if not isinstance(answer, dict):
        return {"records": [], "totalCount": 0}

    # Parse standard reporter response
    raw_records = answer.get("records")
    if not isinstance(raw_records, list):
        return {"records": [], "totalCount": 0}

    records: list[JSONObject] = []
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue

        # Extract primary key
        pk = rec.get("id") or rec.get("primaryKey")
        gene_id = ""
        if isinstance(pk, list) and pk:
            first_pk = pk[0]
            if isinstance(first_pk, dict):
                gene_id = str(first_pk.get("value", "")).strip()

        # Extract attributes
        rec_attrs = rec.get("attributes")
        if not isinstance(rec_attrs, dict):
            rec_attrs = {}

        records.append(
            {
                "geneId": gene_id or rec_attrs.get("primary_key", ""),
                "product": rec_attrs.get("gene_product", ""),
                "organism": rec_attrs.get("organism", ""),
                "geneType": rec_attrs.get("gene_type", ""),
            }
        )

    meta = answer.get("meta") or {}
    total = (
        meta.get("totalCount", len(records)) if isinstance(meta, dict) else len(records)
    )

    return cast(JSONObject, {"records": records, "totalCount": total})
