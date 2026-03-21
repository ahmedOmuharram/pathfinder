"""WDK-based gene search and ID resolution."""

import json
from dataclasses import dataclass
from typing import cast

import pydantic

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search import strip_html_tags
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

from .organism import normalize_organism
from .result import DEFAULT_GENE_ATTRIBUTES, GeneResultInput, build_gene_result

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


def _parse_wdk_record(rec: JSONObject) -> JSONObject | None:
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
        GeneResultInput(
            gene_id=gene_source_id or gene_id,
            display_name=gene_name or product or gene_id,
            organism=org,
            product=product,
            gene_name=gene_name,
            gene_type=gene_type,
            location=location,
            previous_ids=previous_ids or "",
        )
    )


def _accumulate_text_answer(
    answer: object,
    all_results: list[JSONObject],
    wdk_total: int,
) -> int:
    """Parse a WDK GenesByText answer and accumulate results. Returns updated wdk_total."""
    if not isinstance(answer, dict):
        return wdk_total
    try:
        parsed_answer = WDKAnswer.model_validate(answer)
    except pydantic.ValidationError:
        return wdk_total
    wdk_total = max(wdk_total, parsed_answer.meta.total_count)
    for rec in parsed_answer.records:
        if isinstance(rec, dict):
            parsed = _parse_wdk_record(rec)
            if parsed:
                all_results.append(parsed)
    return wdk_total


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

    fields = text_fields or WDK_TEXT_FIELDS_ID
    client = get_wdk_client(site_id)

    all_results: list[JSONObject] = []
    wdk_total: int = 0
    for pattern in expressions:
        answer = await client.post(
            f"/record-types/{record_type}/searches/GenesByText/reports/standard",
            json=cast(
                "JSONObject",
                {
                    "searchConfig": {
                        "parameters": {
                            "text_expression": pattern,
                            "text_fields": json.dumps(fields),
                            "text_search_organism": json.dumps([organism]),
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
        wdk_total = _accumulate_text_answer(answer, all_results, wdk_total)
        if len(all_results) >= limit:
            break

    records = all_results[:limit]
    return WdkTextResult(
        records=records,
        total_count=max(wdk_total, len(records)),
    )


_EMPTY_GENE_RESULT: JSONObject = {"records": [], "totalCount": 0}


def _build_gene_result_from_answer(answer: object) -> JSONObject:
    """Build the final gene result from a WDK answer (or error dict from _fetch_gene_answer)."""
    if not isinstance(answer, dict):
        return _EMPTY_GENE_RESULT
    # _fetch_gene_answer returns an error dict when dataset creation fails
    if "error" in answer and "records" in answer:
        return answer
    try:
        parsed_answer = WDKAnswer.model_validate(answer)
    except pydantic.ValidationError:
        return _EMPTY_GENE_RESULT
    return _parse_records_to_result(parsed_answer)


def _parse_records_to_result(answer: WDKAnswer) -> JSONObject:
    """Parse WDK answer records into the final gene result dict."""
    records: list[JSONObject] = []
    for rec in answer.records:
        if isinstance(rec, dict):
            parsed = _parse_wdk_record(rec)
            if parsed:
                records.append(parsed)
    return cast("JSONObject", {"records": records, "totalCount": answer.meta.total_count})


def _empty_gene_result(error: str | None = None) -> JSONObject:
    """Return an empty gene result dict, optionally with an error message."""
    if error:
        return {"records": [], "totalCount": 0, "error": error}
    return _EMPTY_GENE_RESULT


async def _fetch_gene_answer(
    client: VEuPathDBClient,
    gene_ids: list[str],
    record_type: str,
    search_name: str,
    param_name: str,
    attrs: list[str],
) -> JSONObject | None:
    """Create a WDK dataset for gene_ids and run a standard reporter query.

    Returns the raw answer dict, or None / error-dict if a step fails.
    Returns a JSONObject with 'error' key on dataset failure.
    """
    dataset_resp = await client.post(
        "/users/current/datasets",
        json=cast(
            "JSONObject",
            {"sourceType": "idList", "sourceContent": {"ids": gene_ids}},
        ),
    )
    if not isinstance(dataset_resp, dict):
        return _empty_gene_result("Failed to create dataset for ID lookup.")
    dataset_id = dataset_resp.get("id")
    if dataset_id is None:
        return _empty_gene_result("Dataset creation returned no ID.")

    result = await client.post(
        f"/record-types/{record_type}/searches/{search_name}/reports/standard",
        json=cast(
            "JSONObject",
            {
                "searchConfig": {"parameters": {param_name: str(dataset_id)}},
                "reportConfig": {"attributes": attrs, "tables": []},
            },
        ),
    )
    if not isinstance(result, dict):
        return None
    return result


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

    Uses a dedicated short-lived WDK client to guarantee session affinity
    between dataset creation and the subsequent search. The shared singleton
    client's cookie jar is modified by concurrent requests, which can cause
    the dataset to "not belong" to the search session (WDK tracks anonymous
    users via session cookies).
    """
    if not gene_ids:
        return _empty_gene_result()

    router = get_site_router()
    site = router.get_site(site_id)
    settings = get_settings()
    routing = router._config.routing
    timeout = float(
        routing.portal_timeout if site.is_portal else routing.component_timeout
    )

    client = VEuPathDBClient(
        base_url=site.service_url,
        timeout=timeout,
        auth_token=settings.veupathdb_auth_token,
    )
    attrs = attributes or DEFAULT_GENE_ATTRIBUTES

    try:
        answer = await _fetch_gene_answer(
            client, gene_ids, record_type, search_name, param_name, attrs
        )
    except AppError as exc:
        logger.warning(
            "Gene ID resolution via standard reporter failed",
            site_id=site_id,
            gene_ids_count=len(gene_ids),
            error=str(exc),
        )
        return _empty_gene_result(f"WDK lookup failed: {exc}")
    finally:
        await client.close()

    return _build_gene_result_from_answer(answer)
