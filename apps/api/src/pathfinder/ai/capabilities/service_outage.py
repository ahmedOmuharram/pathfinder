from __future__ import annotations

from dataclasses import dataclass, field

# A search is abandoned once it has failed this many times in a turn. The
# resilience layer retries below the threshold; at or above it the search is
# both reported as unavailable AND withdrawn from the tools' search_name enum,
# so the model cannot keep re-selecting something that is down upstream.
OUTAGE_GIVE_UP_THRESHOLD = 2


@dataclass
class ServiceOutageMemory:
    """Run-scoped memory of which searches have hit transient (5xx) errors this
    turn. Lets ToolResilience abandon a persistently-unavailable search instead
    of telling the model to retry it forever.

    Counts are keyed by SEARCH NAME, not by (tool, search): a 500 is a property
    of the search, so a failure seen through ``get_search_overview`` and one
    through ``set_criterion`` are the same outage and must add up.
    """

    _counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def record_search_failure(self, search_name: str) -> int:
        """Record one transient failure; returns the running count."""
        self._counts[search_name] = self._counts.get(search_name, 0) + 1
        return self._counts[search_name]

    def unavailable_searches(self) -> frozenset[str]:
        """Searches abandoned for the rest of this turn."""
        return frozenset(
            name
            for name, seen in self._counts.items()
            if seen >= OUTAGE_GIVE_UP_THRESHOLD
        )
