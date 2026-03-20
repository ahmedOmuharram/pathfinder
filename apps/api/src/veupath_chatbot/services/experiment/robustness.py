"""Bootstrap robustness and uncertainty estimation.

Resamples control sets with replacement and recomputes rank metrics
to derive confidence intervals and stability scores — all pure Python,
no additional WDK API calls required.
"""

import random
from collections import defaultdict

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
)
from veupath_chatbot.services.experiment.rank_metrics import compute_rank_metrics
from veupath_chatbot.services.experiment.types import (
    DEFAULT_K_VALUES,
    BootstrapResult,
    ConfidenceInterval,
    NegativeSetVariant,
)

logger = get_logger(__name__)

_MIN_SETS_FOR_JACCARD = 2


class _SeededRNG(random.Random):
    """Deterministic PRNG for statistical sampling (not security use)."""


def compute_robustness(
    result_ids: list[str],
    positive_ids: list[str],
    negative_ids: list[str],
    *,
    n_bootstrap: int = 200,
    k_values: list[int] | None = None,
    seed: int = 42,
    alternative_negatives: dict[str, list[str]] | None = None,
    include_rank_metrics: bool = True,
) -> BootstrapResult:
    """Compute bootstrap confidence intervals for classification (and optionally rank) metrics.

    :param result_ids: Ordered gene IDs from the strategy result.
    :param positive_ids: Positive control gene IDs.
    :param negative_ids: Negative control gene IDs.
    :param n_bootstrap: Number of bootstrap iterations.
    :param k_values: K values for Precision/Recall/Enrichment@K.
    :param seed: Random seed for reproducibility.
    :param alternative_negatives: Optional map of label -> negative IDs for
        negative-set sensitivity analysis.
    :param include_rank_metrics: When ``False``, skip rank metric CIs and
        top-K stability — only classification CIs are computed.
    :returns: Bootstrap robustness result.
    """
    if k_values is None:
        k_values = DEFAULT_K_VALUES

    rng = _SeededRNG(seed)

    metric_samples: dict[str, list[float]] = defaultdict(list)
    rank_metric_samples: dict[str, list[float]] = defaultdict(list)
    top_k_sets: list[set[str]] = []

    pos_list = list(positive_ids)
    neg_list = list(negative_ids)

    for _ in range(n_bootstrap):
        boot_pos = _resample(pos_list, rng)
        boot_neg = _resample(neg_list, rng)

        if include_rank_metrics:
            boot_pos_set = set(boot_pos)
            boot_neg_set = set(boot_neg)
            rm = compute_rank_metrics(
                result_ids=result_ids,
                positive_ids=boot_pos_set,
                negative_ids=boot_neg_set,
                k_values=k_values,
            )

            for kv in k_values:
                rank_metric_samples[f"precision_at_{kv}"].append(
                    rm.precision_at_k.get(kv, 0.0)
                )
                rank_metric_samples[f"recall_at_{kv}"].append(
                    rm.recall_at_k.get(kv, 0.0)
                )
                rank_metric_samples[f"enrichment_at_{kv}"].append(
                    rm.enrichment_at_k.get(kv, 0.0)
                )

            stability_k = 50
            # Use the bootstrapped positive set to determine which of the
            # top-K results are "relevant" — this varies across iterations,
            # producing a meaningful stability estimate.
            top_k_ids = result_ids[:stability_k]
            boot_relevant = {gid for gid in top_k_ids if gid in boot_pos_set}
            top_k_sets.append(boot_relevant)

        _collect_classification_metrics(
            result_ids, set(boot_pos), set(boot_neg), metric_samples
        )

    metric_cis = {k: _ci_from_samples(v) for k, v in metric_samples.items()}
    rank_metric_cis = {k: _ci_from_samples(v) for k, v in rank_metric_samples.items()}

    top_k_stability = _mean_jaccard(top_k_sets) if top_k_sets else 0.0

    neg_variants: list[NegativeSetVariant] = []
    if include_rank_metrics and alternative_negatives:
        for label, alt_neg in alternative_negatives.items():
            rm = compute_rank_metrics(
                result_ids=result_ids,
                positive_ids=set(positive_ids),
                negative_ids=set(alt_neg),
                k_values=k_values,
            )
            neg_variants.append(
                NegativeSetVariant(
                    label=label,
                    negative_count=len(alt_neg),
                    rank_metrics=rm,
                )
            )

    return BootstrapResult(
        n_iterations=n_bootstrap,
        metric_cis=metric_cis,
        rank_metric_cis=rank_metric_cis,
        top_k_stability=top_k_stability,
        negative_set_sensitivity=neg_variants,
    )


def _resample(items: list[str], rng: random.Random) -> list[str]:
    """Resample with replacement."""
    n = len(items)
    if n == 0:
        return []
    return [items[rng.randint(0, n - 1)] for _ in range(n)]


def _collect_classification_metrics(
    result_ids: list[str],
    pos_set: set[str],
    neg_set: set[str],
    samples: dict[str, list[float]],
) -> None:
    """Compute binary classification metrics and accumulate into samples dict."""
    result_set = set(result_ids)
    cm = compute_confusion_matrix(
        positive_hits=len(pos_set & result_set),
        total_positives=len(pos_set),
        negative_hits=len(neg_set & result_set),
        total_negatives=len(neg_set),
    )
    m = compute_metrics(cm)

    samples["sensitivity"].append(m.sensitivity)
    samples["specificity"].append(m.specificity)
    samples["precision"].append(m.precision)
    samples["f1_score"].append(m.f1_score)


def _ci_from_samples(
    samples: list[float],
    alpha: float = 0.05,
) -> ConfidenceInterval:
    """Compute percentile-based confidence interval."""
    if not samples:
        return ConfidenceInterval(lower=0.0, mean=0.0, upper=0.0, std=0.0)
    n = len(samples)
    sorted_s = sorted(samples)
    lo_idx = max(0, int(n * alpha / 2))
    hi_idx = min(n - 1, int(n * (1 - alpha / 2)))
    mean = sum(sorted_s) / n
    variance = sum((x - mean) ** 2 for x in sorted_s) / max(n - 1, 1)
    std = variance**0.5
    return ConfidenceInterval(
        lower=sorted_s[lo_idx],
        mean=mean,
        upper=sorted_s[hi_idx],
        std=std,
    )


def _mean_jaccard(sets: list[set[str]]) -> float:
    """Average pairwise Jaccard similarity (sampled for efficiency)."""
    if len(sets) < _MIN_SETS_FOR_JACCARD:
        return 1.0
    n = len(sets)
    max_pairs = 200
    rng = _SeededRNG(0)
    total = 0.0
    count = 0
    for _ in range(max_pairs):
        indices = rng.sample(range(n), 2)
        i, j = indices[0], indices[1]
        inter = len(sets[i] & sets[j])
        union = len(sets[i] | sets[j])
        if union > 0:
            total += inter / union
            count += 1
    return total / count if count > 0 else 1.0
