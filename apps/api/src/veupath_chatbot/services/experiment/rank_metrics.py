"""Rank-based evaluation metrics (Precision@K, Recall@K, Enrichment@K).

These metrics treat gene lists as ranked outputs rather than binary
classifiers, which better matches how researchers use strategy results
("how many known positives are in my top K?").
"""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    DEFAULT_K_VALUES,
    RankMetrics,
)

logger = get_logger(__name__)

_PR_CURVE_SAMPLE_POINTS = 50


def compute_rank_metrics(
    result_ids: list[str],
    positive_ids: set[str],
    negative_ids: set[str],
    k_values: list[int] | None = None,
) -> RankMetrics:
    """Compute rank-based metrics from an ordered result list.

    All computation is pure Python — no API calls.

    :param result_ids: Ordered gene IDs from the strategy result.
    :param positive_ids: Known positive control gene IDs.
    :param negative_ids: Known negative control gene IDs (unused for rank
        metrics but kept for interface consistency).
    :param k_values: List sizes at which to compute P@K / R@K / E@K.
    :returns: Rank metrics object.
    """
    if k_values is None:
        k_values = DEFAULT_K_VALUES

    total = len(result_ids)
    total_pos = len(positive_ids)
    if total == 0 or total_pos == 0:
        return RankMetrics(total_results=total)

    random_precision = total_pos / total if total > 0 else 0.0

    precision_at_k: dict[int, float] = {}
    recall_at_k: dict[int, float] = {}
    enrichment_at_k: dict[int, float] = {}

    cumulative_hits = 0
    pr_curve: list[tuple[float, float]] = []
    list_size_vs_recall: list[tuple[int, float]] = []

    sample_step = max(1, total // _PR_CURVE_SAMPLE_POINTS)

    for i, gene_id in enumerate(result_ids):
        k = i + 1
        if gene_id in positive_ids:
            cumulative_hits += 1

        prec = cumulative_hits / k
        rec = cumulative_hits / total_pos

        if k in k_values:
            precision_at_k[k] = prec
            recall_at_k[k] = rec
            enrichment_at_k[k] = (
                (prec / random_precision) if random_precision > 0 else 0.0
            )

        if k % sample_step == 0 or k == total:
            pr_curve.append((prec, rec))
            list_size_vs_recall.append((k, rec))

    for kv in k_values:
        if kv not in precision_at_k:
            effective_k = min(kv, total)
            hits_at_k = sum(
                1 for gid in result_ids[:effective_k] if gid in positive_ids
            )
            precision_at_k[kv] = hits_at_k / effective_k if effective_k > 0 else 0.0
            recall_at_k[kv] = hits_at_k / total_pos if total_pos > 0 else 0.0
            enrichment_at_k[kv] = (
                (precision_at_k[kv] / random_precision) if random_precision > 0 else 0.0
            )

    return RankMetrics(
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
        enrichment_at_k=enrichment_at_k,
        pr_curve=pr_curve,
        list_size_vs_recall=list_size_vs_recall,
        total_results=total,
    )


async def fetch_ordered_result_ids(
    site_id: str,
    step_id: int,
    max_results: int = 5000,
    sort_attribute: str | None = None,
    sort_direction: str = "ASC",
) -> list[str]:
    """Fetch ordered gene IDs from a persisted WDK strategy step.

    When *sort_attribute* is provided the results are sorted by
    ``reportConfig.sorting`` via :meth:`get_step_records`; otherwise
    the default WDK ordering is used (via :meth:`get_step_answer`).

    :param site_id: VEuPathDB site ID.
    :param step_id: WDK step ID.
    :param max_results: Maximum number of IDs to retrieve.
    :param sort_attribute: WDK attribute name to sort by.
    :param sort_direction: ``"ASC"`` or ``"DESC"``.
    :returns: Ordered list of primary key values.
    """
    api = get_strategy_api(site_id)

    sorting: list[JSONObject] | None = None
    if sort_attribute:
        sorting = [{"attributeName": sort_attribute, "direction": sort_direction}]

    if sorting is not None:
        answer: JSONObject = await api.get_step_records(
            step_id=step_id,
            attributes=[],
            pagination={"offset": 0, "numRecords": max_results},
            sorting=sorting,
        )
    else:
        answer = await api.get_step_answer(
            step_id=step_id,
            attributes=[],
            pagination={"offset": 0, "numRecords": max_results},
        )

    records = answer.get("records", [])
    if not isinstance(records, list):
        return []

    ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        pk = rec.get("id")
        if isinstance(pk, list):
            for entry in pk:
                if isinstance(entry, dict):
                    val = entry.get("value")
                    if isinstance(val, str):
                        ids.append(val)
                        break
        elif isinstance(pk, str):
            ids.append(pk)
    return ids
