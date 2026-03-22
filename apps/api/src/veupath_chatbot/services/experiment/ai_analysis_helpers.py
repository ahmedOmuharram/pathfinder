"""Helper functions for experiment analysis AI tools.

Utility functions for extracting WDK record data, classifying genes,
searching records, and fetching result IDs.
"""

from veupath_chatbot.integrations.veupathdb.factory import get_site
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.wdk.helpers import extract_pk

logger = get_logger(__name__)


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


async def build_primary_key(
    api: StrategyAPI, site_id: str, record_type: str, gene_id: str
) -> list[dict[str, str]]:
    """Build a complete WDK primary key for a gene ID.

    WDK requires all primary key columns (e.g. ``source_id`` + ``project_id``
    for gene records). This helper fetches the record type info and fills
    missing columns from site configuration.

    :param api: Strategy API instance.
    :param site_id: VEuPathDB site identifier.
    :param record_type: WDK record type.
    :param gene_id: Gene identifier (the ``source_id`` value).
    :returns: List of ``{name, value}`` dicts forming the complete PK.
    """
    pk_parts: list[dict[str, str]] = [{"name": "source_id", "value": gene_id}]
    try:
        info = await api.get_record_type_info(record_type)
        pk_refs = info.primary_key_column_refs
        if len(pk_parts) < len(pk_refs):
            names_sent = {"source_id"}
            site = get_site(site_id)
            pk_defaults: dict[str, str] = {"project_id": site.project_id}
            for col in pk_refs:
                if col in names_sent:
                    continue
                default_val = pk_defaults.get(col)
                if default_val:
                    pk_parts.append({"name": col, "value": default_val})
    except AppError as exc:
        logger.debug(
            "Failed to build full primary key, falling back to source_id only",
            gene_id=gene_id,
            error=str(exc),
        )
    return pk_parts


async def fetch_group_records(
    api: StrategyAPI,
    record_type: str,
    gene_ids: list[str],
    limit: int = 20,
    site_id: str | None = None,
) -> list[JSONObject]:
    """Fetch records for a list of gene IDs.

    :param api: Strategy API instance.
    :param record_type: WDK record type.
    :param gene_ids: Gene IDs to fetch.
    :param limit: Max number of genes to fetch.
    :param site_id: Site ID for PK completion (fills project_id etc.).
    :returns: List of dicts with ``geneId`` and ``attributes``.
    """
    results: list[JSONObject] = []
    for gene_id in gene_ids[:limit]:
        try:
            if site_id:
                pk = await build_primary_key(api, site_id, record_type, gene_id)
            else:
                pk = [{"name": "source_id", "value": gene_id}]
            rec = await api.get_single_record(
                record_type=record_type,
                primary_key=pk,
            )
            results.append(
                {
                    "geneId": gene_id,
                    "attributes": rec.attributes,
                }
            )
        except AppError as exc:
            logger.debug(
                "Failed to fetch record for gene", gene_id=gene_id, error=str(exc)
            )
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
        records = answer.records
        if not records:
            break
        for rec in records:
            gene_id = extract_pk(rec)
            if gene_id:
                result_ids.add(gene_id)
        offset += len(records)
        if len(records) < page_size:
            break

    return result_ids
