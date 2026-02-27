"""Helper functions for experiment analysis AI tools.

Utility functions for extracting WDK record data, classifying genes,
searching records, and fetching result IDs.
"""

from __future__ import annotations

from typing import cast

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.types import JSONObject


def extract_pk(record: JSONObject) -> str | None:
    """Extract primary key string from a WDK record.

    :param record: WDK record dict with ``id`` array.
    :returns: First primary key value, or None.
    """
    pk = record.get("id")
    if isinstance(pk, list) and pk:
        first = pk[0]
        if isinstance(first, dict):
            val = first.get("value")
            if isinstance(val, str):
                return val.strip()
    return None


def classify_gene(
    gene_id: str | None,
    tp_ids: set[str],
    fp_ids: set[str],
    fn_ids: set[str],
    tn_ids: set[str],
) -> str | None:
    """Return the classification label for a gene ID.

    :param gene_id: Gene identifier to classify.
    :param tp_ids: True positive gene IDs.
    :param fp_ids: False positive gene IDs.
    :param fn_ids: False negative gene IDs.
    :param tn_ids: True negative gene IDs.
    :returns: One of ``"TP"``, ``"FP"``, ``"FN"``, ``"TN"``, or None.
    """
    if not gene_id:
        return None
    if gene_id in tp_ids:
        return "TP"
    if gene_id in fp_ids:
        return "FP"
    if gene_id in fn_ids:
        return "FN"
    if gene_id in tn_ids:
        return "TN"
    return None


def record_matches(attrs: JSONObject, query_lower: str, attribute: str | None) -> bool:
    """Check if a record's attributes match a text query.

    :param attrs: Record attribute dict.
    :param query_lower: Lowercased search query.
    :param attribute: Specific attribute to search in, or None for all.
    :returns: True if any matching attribute value is found.
    """
    if attribute:
        val = attrs.get(attribute)
        return isinstance(val, str) and query_lower in val.lower()
    return any(isinstance(v, str) and query_lower in v.lower() for v in attrs.values())


async def fetch_group_records(
    api: StrategyAPI, record_type: str, gene_ids: list[str], limit: int = 20
) -> list[JSONObject]:
    """Fetch records for a list of gene IDs.

    :param api: Strategy API instance.
    :param record_type: WDK record type.
    :param gene_ids: Gene IDs to fetch.
    :param limit: Max number of genes to fetch.
    :returns: List of dicts with ``geneId`` and ``attributes``.
    """
    results: list[JSONObject] = []
    for gene_id in gene_ids[:limit]:
        try:
            rec = await api.get_single_record(
                record_type=record_type,
                primary_key=cast(
                    list[JSONObject], [{"name": "source_id", "value": gene_id}]
                ),
            )
            if isinstance(rec, dict):
                results.append(
                    {
                        "geneId": gene_id,
                        "attributes": rec.get("attributes", {}),
                    }
                )
        except Exception:
            continue
    return results


async def collect_all_result_ids(api: StrategyAPI, step_id: int) -> set[str]:
    """Fetch all result gene IDs from a WDK step by paginating.

    :param api: Strategy API instance.
    :param step_id: WDK step ID.
    :returns: Set of all gene IDs in the step's results.
    """
    result_ids: set[str] = set()
    offset = 0
    page_size = 1000

    while True:
        answer = await api.get_step_records(
            step_id=step_id,
            attributes=[],
            pagination={"offset": offset, "numRecords": page_size},
        )
        records = answer.get("records", [])
        if not isinstance(records, list) or not records:
            break
        for rec in records:
            gene_id = extract_pk(rec)
            if gene_id:
                result_ids.add(gene_id)
        offset += len(records)
        if len(records) < page_size:
            break

    return result_ids
