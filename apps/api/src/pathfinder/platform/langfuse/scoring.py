"""Emit evaluation metrics as Langfuse scores on traces."""

import langfuse.api

from pathfinder.platform.langfuse.client import get_langfuse
from pathfinder.platform.logging import get_logger
from pathfinder.services.experiment.types import ExperimentMetrics

logger = get_logger(__name__)

# Langfuse SDK can raise langfuse.api.Error (API/network), ValueError
# (invalid args), or OSError (DNS/socket).
_LANGFUSE_ERRORS = (langfuse.api.Error, ValueError, OSError)


def emit_evaluation_scores(trace_id: str, metrics: ExperimentMetrics) -> None:
    """Push evaluation metrics as Langfuse scores. No-op when disabled."""
    client = get_langfuse()
    if client is None:
        return

    scores: dict[str, float] = {
        "sensitivity": metrics.sensitivity,
        "specificity": metrics.specificity,
        "precision": metrics.precision,
        "f1_score": metrics.f1_score,
        "mcc": metrics.mcc,
        "balanced_accuracy": metrics.balanced_accuracy,
        "youdens_j": metrics.youdens_j,
    }

    for name, value in scores.items():
        try:
            client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                data_type="NUMERIC",
            )
        except _LANGFUSE_ERRORS:
            logger.warning("Failed to emit Langfuse score", name=name, exc_info=True)

    logger.debug(
        "Emitted evaluation scores to Langfuse",
        trace_id=trace_id,
        count=len(scores),
    )
