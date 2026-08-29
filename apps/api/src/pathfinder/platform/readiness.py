"""Readiness-state tracking for the API lifecycle.

A single process-wide :class:`ReadinessState` records the init status of
every subsystem that must be up before the API can faithfully serve
requests: database, embedding backend, PIGuard, graph checkpointer, and
each site catalog. ``/health/ready`` consults this state to return
200/503.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_FIXED_SUBSYSTEMS = (
    "database",
    "embedding_backend",
    "piguard",
    "graph_checkpointer",
)


class SubsystemStatus(BaseModel):
    """Per-subsystem readiness record."""

    ready: bool = False
    error: str | None = None


class ReadinessState(BaseModel):
    """Aggregate readiness for the whole API process."""

    database: SubsystemStatus = Field(default_factory=SubsystemStatus)
    embedding_backend: SubsystemStatus = Field(default_factory=SubsystemStatus)
    piguard: SubsystemStatus = Field(default_factory=SubsystemStatus)
    graph_checkpointer: SubsystemStatus = Field(default_factory=SubsystemStatus)
    catalogs: dict[str, SubsystemStatus] = Field(default_factory=dict)

    @property
    def all_ready(self) -> bool:
        return (
            self.database.ready
            and self.embedding_backend.ready
            and self.piguard.ready
            and self.graph_checkpointer.ready
            and all(c.ready for c in self.catalogs.values())
        )

    @property
    def not_ready(self) -> list[str]:
        missing = [name for name in _FIXED_SUBSYSTEMS if not getattr(self, name).ready]
        missing.extend(
            f"catalog:{site_id}" for site_id, c in self.catalogs.items() if not c.ready
        )
        return missing

    def mark_ready(self, subsystem: str) -> None:
        if subsystem not in _FIXED_SUBSYSTEMS:
            msg = f"unknown subsystem: {subsystem}"
            raise ValueError(msg)
        setattr(self, subsystem, SubsystemStatus(ready=True))

    def mark_failed(self, subsystem: str, error: str) -> None:
        if subsystem not in _FIXED_SUBSYSTEMS:
            msg = f"unknown subsystem: {subsystem}"
            raise ValueError(msg)
        setattr(self, subsystem, SubsystemStatus(ready=False, error=error))

    def register_catalog(self, site_id: str) -> None:
        self.catalogs[site_id] = SubsystemStatus()

    def mark_catalog_ready(self, site_id: str) -> None:
        self.catalogs[site_id] = SubsystemStatus(ready=True)

    def mark_catalog_failed(self, site_id: str, error: str) -> None:
        self.catalogs[site_id] = SubsystemStatus(ready=False, error=error)


_state_holder: dict[str, ReadinessState] = {}


def get_readiness() -> ReadinessState:
    """Return the process-wide readiness state (lazily constructed)."""
    if "v" not in _state_holder:
        _state_holder["v"] = ReadinessState()
    return _state_holder["v"]


def reset_readiness() -> None:
    """Reset state. For tests and shutdown only."""
    _state_holder.clear()
