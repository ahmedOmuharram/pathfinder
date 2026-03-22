"""Gene record classification by experiment category membership.

Classifies WDK result records as TP / FP / FN / TN based on
whether their gene ID appears in the experiment's curated gene sets.
Handles WDK transcript ID version suffixes (e.g. "GENE.1" -> "GENE").
"""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordInstance
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.wdk.helpers import extract_pk


def classify_records(
    records: list[WDKRecordInstance],
    tp_ids: set[str],
    fp_ids: set[str],
    fn_ids: set[str],
    tn_ids: set[str],
) -> list[JSONObject]:
    """Add ``_classification`` field to records based on gene ID membership.

    For each record, extracts the primary key and checks membership in
    the four gene-set categories.  WDK transcript IDs may include a
    version suffix (e.g. ``"PF3D7_0100100.1"``); the function also
    checks the base ID with the suffix stripped.

    :param records: WDK answer records.
    :param tp_ids: True-positive gene IDs.
    :param fp_ids: False-positive gene IDs.
    :param fn_ids: False-negative gene IDs.
    :param tn_ids: True-negative gene IDs.
    :returns: New list of records, each with a ``_classification`` field.
    """
    classified: list[JSONObject] = []
    for rec in records:
        gene_id = extract_pk(rec)
        classification = _classify_gene_id(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
        classified.append({
            **rec.model_dump(by_alias=True),
            "_classification": classification,
        })
    return classified


def _classify_gene_id(
    gene_id: str | None,
    tp_ids: set[str],
    fp_ids: set[str],
    fn_ids: set[str],
    tn_ids: set[str],
) -> str | None:
    """Return the classification label for a single gene ID, or ``None``."""
    if not gene_id:
        return None

    # WDK transcript IDs include a version suffix (e.g. ".1").
    # Experiment gene sets store the base gene ID without it.
    candidates = [gene_id]
    dot = gene_id.rfind(".")
    if dot > 0:
        candidates.append(gene_id[:dot])

    for gid in candidates:
        if gid in tp_ids:
            return "TP"
        if gid in fp_ids:
            return "FP"
        if gid in fn_ids:
            return "FN"
        if gid in tn_ids:
            return "TN"

    return None
