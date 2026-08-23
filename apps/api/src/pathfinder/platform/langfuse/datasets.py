"""Langfuse dataset management for evaluation experiments."""

from collections.abc import Callable
from typing import Any

import langfuse.api
from assistant_core.platform.logging import get_logger
from pydantic import BaseModel

from pathfinder.platform.langfuse.client import get_langfuse

logger = get_logger(__name__)

# Langfuse SDK can raise langfuse.api.Error (API/network), ValueError
# (invalid args), or OSError (DNS/socket).
_LANGFUSE_ERRORS = (langfuse.api.Error, ValueError, OSError)


class DatasetItemInput(BaseModel):
    """Typed input for seeding a Langfuse dataset item."""

    input: Any
    expected_output: Any = None
    metadata: dict[str, Any] | None = None


def seed_dataset(
    dataset_name: str,
    items: list[DatasetItemInput],
) -> None:
    """Create or update a Langfuse dataset from items. No-op when disabled."""
    client = get_langfuse()
    if client is None:
        return

    try:
        client.create_dataset(name=dataset_name)
    except _LANGFUSE_ERRORS:
        logger.debug("Dataset may already exist", name=dataset_name)

    for item in items:
        try:
            client.create_dataset_item(
                dataset_name=dataset_name,
                input=item.input,
                expected_output=item.expected_output,
                metadata=item.metadata,
            )
        except _LANGFUSE_ERRORS:
            logger.warning("Failed to seed dataset item", exc_info=True)

    logger.info("Dataset seeded", name=dataset_name, count=len(items))


def run_evaluation_experiment(
    *,
    dataset_name: str,
    experiment_name: str,
    task_fn: Callable[..., Any],
) -> Any:
    """Run an evaluation experiment via Langfuse.

    Fetches the dataset by name, then delegates to ``DatasetClient.run_experiment``.
    Evaluations are applied separately via scoring after the task runs.
    Returns ``None`` when Langfuse is disabled.
    """
    client = get_langfuse()
    if client is None:
        logger.warning("Cannot run experiment (Langfuse disabled)")
        return None

    dataset = client.get_dataset(dataset_name)
    return dataset.run_experiment(
        name=experiment_name,
        task=task_fn,
    )
