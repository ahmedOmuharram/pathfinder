"""Shared context and locking for experiment execution phases.

Provides the ``PhaseContext`` dataclass threaded through all phase functions,
the ``EmitFn`` progress-callback type alias, and per-experiment locking to
prevent concurrent mutations.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pathfinder.services.experiment.store import ExperimentStore
from pathfinder.services.experiment.types import (
    Experiment,
    ExperimentConfig,
)

# Type alias for the progress-emit callback threaded through phases.
EmitFn = Callable[..., Awaitable[None]]


@dataclass
class PhaseContext:
    """Shared context threaded through all experiment phases.

    Bundles the four parameters that every phase function receives:
    the experiment configuration, the mutable experiment object,
    the SSE progress-emit callback, and the persistence store.
    """

    config: ExperimentConfig
    experiment: Experiment
    emit: EmitFn
    store: ExperimentStore


# Per-experiment lock to prevent concurrent mutations of the same experiment
# (e.g., DELETE while a run_experiment() is in-flight).
_experiment_locks: dict[str, asyncio.Lock] = {}
_EXPERIMENT_LOCKS_MAX = 200


def get_experiment_lock(experiment_id: str) -> asyncio.Lock:
    """Get or create a per-experiment lock for serialising mutations.

    Uses LRU eviction of unlocked entries to bound memory.  Eviction of
    an unlocked entry is safe: no operation is in-flight for that
    experiment, so a fresh lock will be created if needed later.
    """
    if experiment_id in _experiment_locks:
        return _experiment_locks[experiment_id]

    if len(_experiment_locks) >= _EXPERIMENT_LOCKS_MAX:
        to_evict: str | None = None
        for cand_id, lock in _experiment_locks.items():
            if not lock.locked():
                to_evict = cand_id
                break
        if to_evict is not None:
            del _experiment_locks[to_evict]

    _experiment_locks[experiment_id] = asyncio.Lock()
    return _experiment_locks[experiment_id]
