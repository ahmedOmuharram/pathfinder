"""Searches that are down upstream must leave the FRAME enum.

A live turn spent 10 of its 35 tool calls re-selecting two searches that
VectorBase was 500ing on (``..._Houri_aegypti_2023_..._DESeq`` and its
``Percentile`` sibling). PathFinder marked them ``SEARCH_UNAVAILABLE`` and then
kept offering them in the ``search_name`` enum, so the model had no way to stop
choosing them -- each attempt looked newly worth trying.

The outage itself is upstream and not PathFinder's to fix. Re-offering a search
already given up on this turn is.
"""

from __future__ import annotations

from pathfinder.ai.capabilities.service_outage import ServiceOutageMemory
from pathfinder.ai.tools.toolsets.frame import _frame_enum_overrides

_ENUM_KEYS = (
    ("get_search_overview", "search_name"),
    ("set_criterion", "search_name"),
    ("get_parameter_options", "search_name"),
)

UP = "GenesByRNASeqaaegLVP_AGWG_SRP047470_ebi_rnaSeq_RSRCDESeq"
DOWN = "GenesByRNASeqaaegLVP_AGWG_Houri_aegypti_2023_ebi_rnaSeq_RSRCDESeq"
DOWN_SIBLING = "GenesByRNASeqaaegLVP_AGWG_Houri_aegypti_2023_ebi_rnaSeq_RSRCPercentile"


class _State:
    def __init__(self, candidates: list[str]) -> None:
        self._candidates = candidates

    def candidate_search_names(self) -> list[str]:
        return self._candidates

    def discovered_search_names(self) -> list[str]:
        return []


class _Deps:
    def __init__(self, candidates: list[str], outage: ServiceOutageMemory) -> None:
        self.agent_state = _State(candidates)
        self.service_outage = outage


class _Ctx:
    def __init__(self, deps: _Deps) -> None:
        self.deps = deps


def _overrides(candidates: list[str], outage: ServiceOutageMemory) -> dict:
    return _frame_enum_overrides(_Ctx(_Deps(candidates, outage)))  # type: ignore[arg-type]


def _give_up_on(outage: ServiceOutageMemory, search: str) -> None:
    """Record enough failures that the resilience layer abandons the search."""
    outage.record_search_failure(search)
    outage.record_search_failure(search)


def test_a_search_given_up_on_is_no_longer_offered() -> None:
    outage = ServiceOutageMemory()
    _give_up_on(outage, DOWN)
    overrides = _overrides([UP, DOWN], outage)
    for key in _ENUM_KEYS:
        assert overrides[key] == [UP], f"{key} still offered the dead search"


def test_every_outaged_sibling_is_dropped_together() -> None:
    outage = ServiceOutageMemory()
    _give_up_on(outage, DOWN)
    _give_up_on(outage, DOWN_SIBLING)
    overrides = _overrides([UP, DOWN, DOWN_SIBLING], outage)
    assert overrides[_ENUM_KEYS[0]] == [UP]


def test_a_single_failure_is_not_enough_to_evict() -> None:
    """One 5xx may be a blip; the resilience layer retries before giving up, so
    the enum must not drop a search the model is still allowed to retry."""
    outage = ServiceOutageMemory()
    outage.record_search_failure(DOWN)
    overrides = _overrides([UP, DOWN], outage)
    assert sorted(overrides[_ENUM_KEYS[0]]) == sorted([UP, DOWN])


def test_healthy_searches_are_untouched() -> None:
    outage = ServiceOutageMemory()
    overrides = _overrides([UP, DOWN], outage)
    assert sorted(overrides[_ENUM_KEYS[0]]) == sorted([UP, DOWN])


def test_no_enum_is_imposed_when_every_candidate_is_down() -> None:
    """Handing the model an empty enum would make every call invalid and it
    could not route around the outage at all. Better to offer the full set and
    let the directive explain, than to offer nothing."""
    outage = ServiceOutageMemory()
    _give_up_on(outage, DOWN)
    _give_up_on(outage, DOWN_SIBLING)
    overrides = _overrides([DOWN, DOWN_SIBLING], outage)
    assert overrides == {}


def test_outage_memory_counts_per_search_not_per_tool() -> None:
    """The search is down regardless of which tool touched it, so a failure via
    ``get_search_overview`` and one via ``set_criterion`` must add up."""
    outage = ServiceOutageMemory()
    assert outage.record_search_failure(DOWN) == 1
    assert outage.record_search_failure(DOWN) == 2
    assert DOWN in outage.unavailable_searches()
    assert UP not in outage.unavailable_searches()
