"""In-memory experiment store.

Provides CRUD operations for experiment lifecycle management.
Consistent with the existing ``strategy_session`` pattern.
"""

from __future__ import annotations

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.types import Experiment

logger = get_logger(__name__)


class ExperimentStore:
    """Thread-safe in-memory experiment repository."""

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    def save(self, experiment: Experiment) -> None:
        """Create or update an experiment."""
        self._experiments[experiment.id] = experiment

    def get(self, experiment_id: str) -> Experiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_all(self, site_id: str | None = None) -> list[Experiment]:
        """List experiments, optionally filtered by site.

        :param site_id: Filter by site ID (None returns all).
        :returns: Experiments sorted by creation time (newest first).
        """
        experiments = list(self._experiments.values())
        if site_id:
            experiments = [e for e in experiments if e.config.site_id == site_id]
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        return experiments

    def delete(self, experiment_id: str) -> bool:
        """Delete an experiment.

        :returns: True if the experiment existed and was removed.
        """
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            return True
        return False


_global_store: ExperimentStore | None = None


def get_experiment_store() -> ExperimentStore:
    """Get the global experiment store singleton."""
    global _global_store
    if _global_store is None:
        _global_store = ExperimentStore()
    return _global_store
