from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceOutageMemory:
    """Run-scoped memory of which searches have hit transient (5xx) errors this
    turn. Lets ToolResilience abandon a persistently-unavailable search instead
    of telling the model to retry it forever."""

    _counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def record(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]
