"""Ordering and wire labels for enrichment values that can be None.

A None ratio is unbounded and is the strongest result. A None probability is
not computable and is the weakest evidence.
"""

from collections.abc import Iterable

UNBOUNDED_RATIO_LABEL = "Inf"
NOT_COMPUTABLE_LABEL = "n/a"


def ratio_sort_key(value: float | None) -> tuple[int, float]:
    """Rank an unbounded ratio first, then finite ratios from high to low."""
    return (0, 0.0) if value is None else (1, -value)


def best_ratio(values: Iterable[float | None]) -> float | None:
    """Return the strongest ratio. An unbounded one beats every float."""
    return min(values, key=ratio_sort_key, default=None)


def ratio_cell(value: float | None) -> str | float:
    """Render a ratio for a file or a JSON matrix."""
    return UNBOUNDED_RATIO_LABEL if value is None else round(value, 4)


def probability_cell(value: float | None) -> str | float:
    """Render a probability for a file or a JSON matrix."""
    return "" if value is None else value
