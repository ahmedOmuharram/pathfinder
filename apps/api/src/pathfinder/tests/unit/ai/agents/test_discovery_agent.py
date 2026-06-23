"""Discovery must pin its captured ``param_vocab``; without the notebook
instruction, elision wipes fetched vocab and it re-probes itself in a loop."""

from __future__ import annotations

from pathfinder.ai.agents._instructions import pinned_discovered_searches
from pathfinder.ai.agents.discovery import discovery_agent


def test_discovery_agent_pins_discovered_search_vocabulary() -> None:
    assert pinned_discovered_searches in discovery_agent._instructions
