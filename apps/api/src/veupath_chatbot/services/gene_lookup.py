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


def _normalize_organism(raw: str) -> str:
    """Clean organism string; handle JSON array format from site-search."""
    s = strip_html_tags(raw or "")
    if not s:
        return ""
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            import json as _json

            parsed = _json.loads(s)
            if isinstance(parsed, list) and parsed:
                return strip_html_tags(str(parsed[0])).strip()
        except ValueError, TypeError:
            pass
    return s


# Default attributes to request for gene records via the standard reporter.
_DEFAULT_GENE_ATTRIBUTES = [
    "primary_key",
    "gene_product",
    "organism",
    "gene_type",
]


async def _enrich_sparse_gene_results(
    site_id: str,
    results: list[JSONObject],
    limit: int,
) -> list[JSONObject]:
    """Enrich results that lack organism/product/displayName via WDK standard reporter.

    Site-search only returns ``foundInFields`` for fields where the query matched.
    When a gene matches in literature (e.g. MULTIgene_PubMed), organism/product
    are absent. We fetch full metadata from the WDK to fill the gaps.
    """
    ids_to_enrich: list[str] = [
        str(r["geneId"])
        for r in results
        if isinstance(r, dict)
        and r.get("geneId")
        and (not r.get("organism") or not r.get("product") or not r.get("displayName"))
    ]
    if not ids_to_enrich:
        return results

    try:
        # GeneByLocusTag exists on transcript record type
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
            merged["organism"] = _normalize_organism(str(meta["organism"]))
        if not merged.get("product") and meta.get("product"):
            merged["product"] = strip_html_tags(str(meta["product"]))
        if not merged.get("displayName"):
            merged["displayName"] = str(
                merged.get("product") or meta.get("product") or gene_id or ""
            )
        if not merged.get("project") and meta.get("project"):
            merged["project"] = str(meta["project"])
        enriched.append(merged)

    return enriched[:limit]


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

        # Display name (often the gene symbol or product) — check hyperlinkName and doc-level fields
        display_name = strip_html_tags(str(doc.get("hyperlinkName") or ""))
        if not display_name and doc.get("product"):
            display_name = strip_html_tags(str(doc.get("product", "")))
        if not display_name and doc.get("gene_product"):
            display_name = strip_html_tags(str(doc.get("gene_product", "")))

        # Extract useful fields from foundInFields (only contains fields where query matched)
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
                        _normalize_organism(str(field_values[0]))
                        if field_values
                        else ""
                    )
                elif clean_key in ("product", "gene_product"):
                    product = (
                        strip_html_tags(str(field_values[0])) if field_values else ""
                    )
                if field_values:
                    matched_fields.append(clean_key)

        # Fallback: check doc-level fields (site-search may expose these in some layouts)
        if not organism and doc.get("organism"):
            organism = _normalize_organism(str(doc.get("organism", "")))
        if not organism and doc.get("gene_organism_full"):
            organism = _normalize_organism(str(doc.get("gene_organism_full", "")))
        if not product and doc.get("product"):
            product = strip_html_tags(str(doc.get("product", "")))
        if not product and doc.get("gene_product"):
            product = strip_html_tags(str(doc.get("gene_product", "")))
        if not display_name and product:
            display_name = product

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

    # Enrich sparse results (e.g. when match was only in literature/MULTIgene_PubMed)
    results = await _enrich_sparse_gene_results(site_id, results, limit)

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

        # Extract primary key and attributes
        rec_attrs = rec.get("attributes")
        if not isinstance(rec_attrs, dict):
            rec_attrs = {}

        pk = rec.get("id") or rec.get("primaryKey")
        gene_id = ""
        project = ""
        if isinstance(pk, list):
            for elem in pk:
                if not isinstance(elem, dict):
                    continue
                name = elem.get("name")
                val = elem.get("value")
                if (
                    name in ("gene_source_id", "gene")
                    and isinstance(val, str)
                    and val.strip()
                ):
                    gene_id = val.strip()
                elif name == "project_id" and isinstance(val, str) and val.strip():
                    project = val.strip()
        if not gene_id and isinstance(pk, list) and pk:
            first_pk = pk[0]
            if isinstance(first_pk, dict):
                gene_id = str(first_pk.get("value", "")).strip()
        if not gene_id:
            gene_id = str(rec_attrs.get("primary_key", "")).strip()

        records.append(
            {
                "geneId": gene_id or rec_attrs.get("primary_key", ""),
                "project": project,
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
