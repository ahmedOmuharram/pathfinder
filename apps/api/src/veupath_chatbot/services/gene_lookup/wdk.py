"""WDK-based gene search and ID resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.site_search import strip_html_tags
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

from .organism import normalize_organism
from .result import DEFAULT_GENE_ATTRIBUTES, build_gene_result

logger = get_logger(__name__)

WDK_WILDCARD_LIMIT = 50

WDK_TEXT_FIELDS_ID: list[str] = ["primary_key", "Alias"]
WDK_TEXT_FIELDS_BROAD: list[str] = [
    "product",
    "name",
    "primary_key",
    "Alias",
    "GOTerms",
    "Notes",
    "Products",
]


@dataclass
class WdkTextResult:
    """Results from a WDK ``GenesByText`` query."""

    records: list[JSONObject]
    total_count: int


def _parse_wdk_record(rec: dict) -> JSONObject | None:  # type: ignore[type-arg]
    """Parse a WDK record into a standard gene result dict."""
    rec_attrs = rec.get("attributes")
    if not isinstance(rec_attrs, dict):
        rec_attrs = {}

    pk = rec.get("id")
    gene_id = ""
    if isinstance(pk, list):
        for elem in pk:
            if not isinstance(elem, dict):
                continue
            name = elem.get("name")
            val = elem.get("value")
            if (
                name in ("gene_source_id", "source_id", "gene")
                and isinstance(val, str)
                and val.strip()
            ):
                gene_id = val.strip()
                break
    if not gene_id:
        gene_id = str(rec_attrs.get("primary_key", "")).strip()

    gene_name_raw = rec_attrs.get("gene_name", "")
    gene_name = strip_html_tags(str(gene_name_raw)) if gene_name_raw else ""
    product_raw = rec_attrs.get("gene_product", "")
    product = strip_html_tags(str(product_raw)) if product_raw else ""
    organism_raw = rec_attrs.get("organism", "")
    org = normalize_organism(str(organism_raw)) if organism_raw else ""
    gene_type = str(rec_attrs.get("gene_type", ""))
    location = str(rec_attrs.get("gene_location_text", ""))
    gene_source_id = str(rec_attrs.get("gene_source_id", ""))
    previous_ids = str(rec_attrs.get("gene_previous_ids", ""))

    return build_gene_result(
        gene_id=gene_source_id or gene_id,
        display_name=gene_name or product or gene_id,
        organism=org,
        product=product,
        gene_name=gene_name,
        gene_type=gene_type,
        location=location,
        previous_ids=previous_ids or "",
    )


async def fetch_wdk_text_genes(
    site_id: str,
    expressions: list[str],
    *,
    organism: str | None = None,
    text_fields: list[str] | None = None,
    record_type: str = "transcript",
    limit: int = WDK_WILDCARD_LIMIT,
) -> WdkTextResult:
    """Search genes via WDK ``GenesByText``."""
    if not expressions or not organism:
        return WdkTextResult(records=[], total_count=0)

    import json as _json

    fields = text_fields or WDK_TEXT_FIELDS_ID
    client = get_wdk_client(site_id)

    all_results: list[JSONObject] = []
    wdk_total: int = 0
    for pattern in expressions:
        answer = await client.post(
            f"/record-types/{record_type}/searches/GenesByText/reports/standard",
            json=cast(
                JSONObject,
                {
                    "searchConfig": {
                        "parameters": {
                            "text_expression": pattern,
                            "text_fields": _json.dumps(fields),
                            "text_search_organism": _json.dumps([organism]),
                            "document_type": "gene",
                        },
                    },
                    "reportConfig": {
                        "attributes": DEFAULT_GENE_ATTRIBUTES,
                        "tables": [],
                        "pagination": {"offset": 0, "numRecords": limit},
                    },
                },
            ),
        )
        if not isinstance(answer, dict):
            continue

        meta = answer.get("meta")
        if isinstance(meta, dict):
            mt = meta.get("totalCount")
            if isinstance(mt, int):
                wdk_total = max(wdk_total, mt)

        raw_records = answer.get("records")
        if not isinstance(raw_records, list):
            continue

        for rec in raw_records:
            if not isinstance(rec, dict):
                continue
            parsed = _parse_wdk_record(rec)
            if parsed:
                all_results.append(parsed)

        if len(all_results) >= limit:
            break

    records = all_results[:limit]
    return WdkTextResult(
        records=records,
        total_count=max(wdk_total, len(records)),
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
    """Resolve a list of gene IDs to full records via the WDK standard reporter."""
    if not gene_ids:
        return {"records": [], "totalCount": 0}

    client = get_wdk_client(site_id)
    attrs = attributes or DEFAULT_GENE_ATTRIBUTES

    try:
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

    raw_records = answer.get("records")
    if not isinstance(raw_records, list):
        return {"records": [], "totalCount": 0}

    records: list[JSONObject] = []
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue
        parsed = _parse_wdk_record(rec)
        if parsed:
            records.append(parsed)

    meta = answer.get("meta") or {}
    total = (
        meta.get("totalCount", len(records)) if isinstance(meta, dict) else len(records)
    )

    return cast(JSONObject, {"records": records, "totalCount": total})
